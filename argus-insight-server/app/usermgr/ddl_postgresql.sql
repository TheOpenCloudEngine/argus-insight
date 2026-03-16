-- User management tables for PostgreSQL

CREATE TABLE IF NOT EXISTS argus_roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS argus_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(30),
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    role_id INTEGER NOT NULL REFERENCES argus_roles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed roles
INSERT INTO argus_roles (name, description) VALUES ('Admin', 'Administrator with full access') ON CONFLICT (name) DO NOTHING;
INSERT INTO argus_roles (name, description) VALUES ('User', 'Standard user with limited access') ON CONFLICT (name) DO NOTHING;
