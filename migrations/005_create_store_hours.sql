-- ============================================================
-- Store opening hours: one fixed row per weekday.
-- day_of_week follows MySQL DAYOFWEEK()-1 / JS getDay(): 0 = Sunday .. 6 = Saturday.
-- is_closed = 1 means the shop is shut that day; open_time/close_time are then ignored.
-- Times are interpreted in the store's configured timezone, not the server's.
-- ============================================================

CREATE TABLE IF NOT EXISTS store_hours (
    day_of_week TINYINT      NOT NULL PRIMARY KEY,
    open_time   TIME         NOT NULL DEFAULT '09:00:00',
    close_time  TIME         NOT NULL DEFAULT '18:00:00',
    is_closed   TINYINT(1)   NOT NULL DEFAULT 0,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_store_hours_day CHECK (day_of_week BETWEEN 0 AND 6)
);

-- Seed all seven days so the admin edit form always has a full week to render.
-- Saturday (6) starts closed — adjust from the admin UI.
INSERT IGNORE INTO store_hours (day_of_week, open_time, close_time, is_closed) VALUES
(0, '09:00:00', '18:00:00', 0),
(1, '09:00:00', '18:00:00', 0),
(2, '09:00:00', '18:00:00', 0),
(3, '09:00:00', '18:00:00', 0),
(4, '09:00:00', '18:00:00', 0),
(5, '09:00:00', '14:00:00', 0),
(6, '09:00:00', '18:00:00', 1);
