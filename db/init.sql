-- cq_house 数据库初始化 DDL
USE cq_house;

-- 1. 行政区划表
CREATE TABLE districts (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50)  NOT NULL,
    pinyin      VARCHAR(100),
    level       TINYINT DEFAULT 1,
    is_urban    TINYINT(1) DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. 小区表
CREATE TABLE communities (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    district_id     INT,
    address         VARCHAR(500),
    building_year   INT,
    property_type   VARCHAR(50),
    property_fee    DECIMAL(10,2),
    developer       VARCHAR(200),
    building_count  INT,
    household_count INT,
    green_rate      DECIMAL(5,2),
    plot_ratio      DECIMAL(5,2),
    lng             DECIMAL(10,7),
    lat             DECIMAL(10,7),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (district_id) REFERENCES districts(id)
) ENGINE=InnoDB;
CREATE INDEX idx_communities_district ON communities(district_id);

-- 3. 房源表（核心表）
CREATE TABLE listings (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    external_id         VARCHAR(100) NOT NULL,
    district_id         INT,
    community_id        INT,
    title               VARCHAR(500),
    source_platform     VARCHAR(100) DEFAULT 'fang.com',
    source_url          VARCHAR(1000),

    total_price         DECIMAL(12,2),
    unit_price          DECIMAL(10,2),

    area                DECIMAL(10,2),
    room_count          TINYINT,
    hall_count          TINYINT,
    bathroom_count      TINYINT,
    floor_level         VARCHAR(20),
    total_floors        SMALLINT,
    orientation         VARCHAR(50),
    decoration          VARCHAR(50),
    building_type       VARCHAR(50),
    building_structure  VARCHAR(50),
    has_elevator        TINYINT(1),
    listing_date        DATE,
    listing_age_days    INT,

    status              VARCHAR(20) DEFAULT 'active',
    status_change_date  DATE,

    md5_hash            VARCHAR(32),
    crawl_batch_id      INT,
    first_seen_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_external_id (external_id),
    FOREIGN KEY (district_id)  REFERENCES districts(id),
    FOREIGN KEY (community_id) REFERENCES communities(id)
) ENGINE=InnoDB;

CREATE INDEX idx_listings_district    ON listings(district_id);
CREATE INDEX idx_listings_community   ON listings(community_id);
CREATE INDEX idx_listings_unit_price  ON listings(unit_price);
CREATE INDEX idx_listings_total_price ON listings(total_price);
CREATE INDEX idx_listings_area        ON listings(area);
CREATE INDEX idx_listings_list_date   ON listings(listing_date);
CREATE INDEX idx_listings_md5         ON listings(md5_hash);
CREATE INDEX idx_listings_dist_status_price ON listings(district_id, status, unit_price);
CREATE INDEX idx_listings_comm_status       ON listings(community_id, status);

-- 4. 价格历史表
CREATE TABLE price_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    listing_id  INT NOT NULL,
    total_price DECIMAL(12,2),
    unit_price  DECIMAL(10,2),
    record_date DATE NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE INDEX idx_price_hist_listing ON price_history(listing_id);
CREATE INDEX idx_price_hist_date    ON price_history(record_date);

-- 5. 爬取批次表
CREATE TABLE crawl_batches (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    type                VARCHAR(20) NOT NULL,
    status              VARCHAR(20) DEFAULT 'pending',
    started_at          TIMESTAMP NULL,
    finished_at         TIMESTAMP NULL,
    total_tasks         INT DEFAULT 0,
    completed_tasks     INT DEFAULT 0,
    new_listings        INT DEFAULT 0,
    updated_listings    INT DEFAULT 0,
    removed_listings    INT DEFAULT 0,
    error_summary       JSON DEFAULT NULL
) ENGINE=InnoDB;

-- 6. 爬取任务明细表
CREATE TABLE crawl_tasks (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    batch_id        INT,
    district_id     INT,
    status          VARCHAR(20) DEFAULT 'pending',
    page_start      INT DEFAULT 1,
    page_end        INT,
    listings_found  INT DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMP NULL,
    finished_at     TIMESTAMP NULL,
    FOREIGN KEY (batch_id)    REFERENCES crawl_batches(id),
    FOREIGN KEY (district_id) REFERENCES districts(id)
) ENGINE=InnoDB;
CREATE INDEX idx_crawl_tasks_batch ON crawl_tasks(batch_id);
