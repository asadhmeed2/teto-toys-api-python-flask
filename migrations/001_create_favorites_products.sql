-- Migration: Create favorites_products table
-- Run this against the shared MySQL database before starting the backend.

CREATE TABLE IF NOT EXISTS favorites_products (
    user_id    VARCHAR(36)  NOT NULL,
    product_id VARCHAR(36)  NOT NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, product_id),
    CONSTRAINT fk_favorites_product
        FOREIGN KEY (product_id) REFERENCES products (product_id)
        ON DELETE CASCADE
);
