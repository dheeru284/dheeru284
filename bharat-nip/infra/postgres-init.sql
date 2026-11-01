-- Runs once, when the postgres volume is first created.
CREATE DATABASE bnip_test OWNER bnip;
\connect bnip
CREATE EXTENSION IF NOT EXISTS vector;
\connect bnip_test
CREATE EXTENSION IF NOT EXISTS vector;
