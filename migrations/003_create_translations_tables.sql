-- ============================================================
-- Translation Table Pattern: per-language text for products,
-- parts, categories and subcategories. Default/fallback language: en
-- ============================================================

CREATE TABLE IF NOT EXISTS product_translations (
    product_id    CHAR(36)     NOT NULL,
    language_code VARCHAR(5)   NOT NULL,
    title         VARCHAR(255) NOT NULL,
    subtitle      VARCHAR(255) NULL,
    description   TEXT         NULL,
    PRIMARY KEY (product_id, language_code),
    CONSTRAINT fk_pt_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS part_translations (
    part_id       CHAR(36)     NOT NULL,
    language_code VARCHAR(5)   NOT NULL,
    title         VARCHAR(255) NOT NULL,
    description   TEXT         NULL,
    PRIMARY KEY (part_id, language_code),
    CONSTRAINT fk_prt_part FOREIGN KEY (part_id) REFERENCES parts(part_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS category_translations (
    category_id   INT          NOT NULL,
    language_code VARCHAR(5)   NOT NULL,
    name          VARCHAR(255) NOT NULL,
    PRIMARY KEY (category_id, language_code),
    CONSTRAINT fk_ct_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subcategory_translations (
    subcategory_id INT          NOT NULL,
    language_code  VARCHAR(5)   NOT NULL,
    name           VARCHAR(255) NOT NULL,
    PRIMARY KEY (subcategory_id, language_code),
    CONSTRAINT fk_sct_subcategory FOREIGN KEY (subcategory_id) REFERENCES subcategories(id) ON DELETE CASCADE
);

-- Backfill existing single-language text into the 'en' row before dropping
-- the old columns. IGNORE makes this safe to re-run by hand.
INSERT IGNORE INTO product_translations (product_id, language_code, title, subtitle, description)
SELECT product_id, 'en', title, subtitle, description FROM products;

INSERT IGNORE INTO part_translations (part_id, language_code, title, description)
SELECT part_id, 'en', title, description FROM parts;

INSERT IGNORE INTO category_translations (category_id, language_code, name)
SELECT id, 'en', name FROM categories;

INSERT IGNORE INTO subcategory_translations (subcategory_id, language_code, name)
SELECT id, 'en', name FROM subcategories;

-- uq_subcat_name(category_id, name) is currently the only index backing the
-- fk_subcat_cat foreign key on category_id, so MySQL refuses to drop it
-- (error 1553) without a replacement index to support that FK first.
CREATE INDEX idx_subcat_category ON subcategories(category_id);

-- Drop the composite unique index BEFORE dropping subcategories.name: dropping
-- the column first would silently narrow this index to UNIQUE(category_id)
-- instead of removing it, breaking creation of a second subcategory per category.
ALTER TABLE subcategories DROP INDEX uq_subcat_name;
ALTER TABLE categories DROP INDEX name;

-- Drop the now-redundant text columns; the translation tables are authoritative.
ALTER TABLE products DROP COLUMN title, DROP COLUMN subtitle, DROP COLUMN description;
ALTER TABLE parts DROP COLUMN title, DROP COLUMN description;
ALTER TABLE categories DROP COLUMN name;
ALTER TABLE subcategories DROP COLUMN name;
