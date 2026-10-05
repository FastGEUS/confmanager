-- Run once on db-srv: sudo -u postgres psql -v ON_ERROR_STOP=1 -f create_database.sql
-- If a role or database already exists, inspect it instead of dropping it.
CREATE ROLE confuser LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
\password confuser
CREATE DATABASE confmanager;
REVOKE ALL ON DATABASE confmanager FROM PUBLIC;
GRANT CONNECT ON DATABASE confmanager TO confuser;
\connect confmanager
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO confuser;
\du confuser
