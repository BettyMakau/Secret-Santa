"""HTTP routes.

/                      create a group
/g/<admin_token>       organizer dashboard (add members, draw, notify)
/m/<access_token>      a member's private page (edit wishlist, see who they're gifting)
"""
from datetime import date, datetime, timezone

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request, url_for,
)

from .draw import DrawError, make_assignments
from .models import Group, Member, db
from .whatsapp import WhatsAppError, click_to_chat_link, normalize_phone, send_message

bp = Blueprint("main", __name__)


def _group_or_404(admin_token: str) -> Group:
    return Group.query.filter_by(admin_token=admin_token).first() or abort(404)


def _member_link(member: Member) -> str:
    base = current_app.config.get("APP_BASE_URL")
    path = url_for("main.member_page", access_token=member.access_token)
    return f"{base}{path}" if base else url_for(
        "main.member_page", access_token=member.access_token, _external=True
    )


def _draw_message(member: Member) -> str:
    g = member.group
    lines = [
        f"Hi {member.name}! 🎅 The *{g.name}* Secret Santa draw is done.",
        "Open your private link to see who you're gifting and their wishlist:",
        _member_link(member),
    ]
    if g.budget:
        lines.append(f"Budget: {g.budget}")
    if g.exchange_date:
        lines.append(f"Gift exchange: {g.exchange_date:%A %d %B %Y}")
    lines.append("Keep it secret! 🤫")
    return "\n".join(lines)


# ---------- Organizer ----------

@bp.get("/")
def index():
    return render_template("index.html")


@bp.post("/groups")
def create_group():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Give your group a name.", "error")
        return redirect(url_for("main.index"))

    exchange_date = None
    if raw := request.form.get("exchange_date"):
        try:
            exchange_date = date.fromisoformat(raw)
        except ValueError:
            flash("That date isn't valid.", "error")
            return redirect(url_for("main.index"))

    group = Group(
        name=name,
        budget=request.form.get("budget", "").strip() or None,
        exchange_date=exchange_date,
    )
    db.session.add(group)
    db.session.commit()
    flash("Group created. Bookmark this page — it's your organizer link.", "success")
    return redirect(url_for("main.admin", admin_token=group.admin_token))


@bp.get("/g/<admin_token>")
def admin(admin_token):
    group = _group_or_404(admin_token)
    wa_links = {}
    if group.is_drawn:
        wa_links = {m.id: click_to_chat_link(m.phone, _draw_message(m)) for m in group.members}
    return render_template("admin.html", group=group, wa_links=wa_links)


@bp.post("/g/<admin_token>/members")
def add_member(admin_token):
    group = _group_or_404(admin_token)
    if group.is_drawn:
        flash("The draw is done — you can't add members now.", "error")
        return redirect(url_for("main.admin", admin_token=admin_token))

    name = request.form.get("name", "").strip()
    try:
        phone = normalize_phone(
            request.form.get("phone", ""), current_app.config["DEFAULT_COUNTRY_CODE"]
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("main.admin", admin_token=admin_token))

    if not name:
        flash("Enter the member's name.", "error")
    elif any(m.phone == phone for m in group.members):
        flash("Someone with that phone number is already in the group.", "error")
    else:
        db.session.add(Member(group=group, name=name, phone=phone))
        db.session.commit()
        flash(f"Added {name}.", "success")
    return redirect(url_for("main.admin", admin_token=admin_token))


@bp.post("/g/<admin_token>/members/<int:member_id>/delete")
def remove_member(admin_token, member_id):
    group = _group_or_404(admin_token)
    member = next((m for m in group.members if m.id == member_id), None) or abort(404)
    if group.is_drawn:
        flash("The draw is done — you can't remove members now.", "error")
    else:
        db.session.delete(member)
        db.session.commit()
        flash(f"Removed {member.name}.", "success")
    return redirect(url_for("main.admin", admin_token=admin_token))


@bp.post("/g/<admin_token>/draw")
def draw(admin_token):
    group = _group_or_404(admin_token)
    if group.is_drawn:
        flash("The draw has already been done.", "error")
        return redirect(url_for("main.admin", admin_token=admin_token))
    try:
        pairs = make_assignments([m.id for m in group.members])
    except DrawError as e:
        flash(str(e), "error")
        return redirect(url_for("main.admin", admin_token=admin_token))

    by_id = {m.id: m for m in group.members}
    for giver_id, recipient_id in pairs.items():
        by_id[giver_id].recipient = by_id[recipient_id]
    group.drawn_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Names drawn! Now send everyone their WhatsApp message.", "success")
    return redirect(url_for("main.admin", admin_token=admin_token))


@bp.post("/g/<admin_token>/notify")
def notify(admin_token):
    group = _group_or_404(admin_token)
    if not group.is_drawn:
        flash("Do the draw first.", "error")
        return redirect(url_for("main.admin", admin_token=admin_token))

    sent, failed = 0, []
    for m in group.members:
        if m.notified_at:
            continue
        try:
            send_message(m.phone, _draw_message(m), current_app.config)
            m.notified_at = datetime.now(timezone.utc)
            sent += 1
        except WhatsAppError as e:
            current_app.logger.warning("WhatsApp send failed for member %s: %s", m.id, e)
            failed.append(m.name)
    db.session.commit()

    if sent:
        flash(f"Sent {sent} WhatsApp message(s).", "success")
    if failed:
        flash("Couldn't message: " + ", ".join(failed) + ". Use their WhatsApp links below.", "error")
    if not sent and not failed:
        flash("Everyone has already been notified.", "info")
    return redirect(url_for("main.admin", admin_token=admin_token))


# ---------- Member ----------

@bp.route("/m/<access_token>", methods=["GET", "POST"])
def member_page(access_token):
    member = Member.query.filter_by(access_token=access_token).first() or abort(404)
    if request.method == "POST":
        member.wishlist = request.form.get("wishlist", "").strip()[:2000]
        db.session.commit()
        flash("Wishlist saved. Your Secret Santa will see it — but not who you are.", "success")
        return redirect(url_for("main.member_page", access_token=access_token))
    return render_template("member.html", member=member, group=member.group)
