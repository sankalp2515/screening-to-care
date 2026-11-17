-- Database per service on one local Postgres server. In production each is its own managed database
-- (or at least its own role and schema), so no service can read another's tables.
CREATE DATABASE notifier;
CREATE DATABASE agent;
