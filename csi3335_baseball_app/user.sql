CREATE OR REPLACE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    pw_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (username, email, pw_hash)
VALUES (
    'admin',
    'admin@example.com',
    'pbkdf2:sha256:600000$zZp3qTNyBgUKjv35XuNLPA==$uUBvOQLJ+Op+nlgXnMcLo1ixFLXnVV5+ktmfklBusrs='
);
