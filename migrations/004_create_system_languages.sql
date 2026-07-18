-- ============================================================
-- System languages lookup: the languages the storefront offers.
-- is_rtl drives the frontend layout direction (Hebrew/Arabic).
-- ============================================================

CREATE TABLE IF NOT EXISTS system_languages (
    code   VARCHAR(5)   PRIMARY KEY,
    name   VARCHAR(100) NOT NULL,
    is_rtl TINYINT(1)   NOT NULL DEFAULT 0
);

INSERT IGNORE INTO system_languages (code, name, is_rtl) VALUES
('en', 'English', 0),
('he', 'עברית', 1),
('ar', 'العربية', 1);
