-- Runs once when the Postgres container is first created.
-- Creates the separate database the test suite uses.
CREATE DATABASE secret_santa_test OWNER santa;
