-- ============================================================
-- 智能用药提醒系统 - MySQL 数据库初始化脚本
-- 数据库名：medication_reminder
-- 字符集：utf8mb4（支持中文及表情符号）
-- 用户：root / 密码：123456
-- ============================================================

-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS `medication_reminder`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `medication_reminder`;

-- ============================================================
-- 2. 用户表 users
-- 存储老人端和家属端的账户信息
-- ============================================================
DROP TABLE IF EXISTS `medication_logs`;
DROP TABLE IF EXISTS `reminders`;
DROP TABLE IF EXISTS `drugs`;
DROP TABLE IF EXISTS `family_relations`;
DROP TABLE IF EXISTS `users`;

CREATE TABLE `users` (
  `id`              INT           NOT NULL AUTO_INCREMENT  COMMENT '用户ID',
  `username`        VARCHAR(50)   NOT NULL                 COMMENT '登录用户名（唯一）',
  `hashed_password` VARCHAR(255)  NOT NULL                 COMMENT 'bcrypt 加密后的密码',
  `display_name`    VARCHAR(100)  NOT NULL                 COMMENT '显示姓名/昵称',
  `role`            VARCHAR(20)   NOT NULL DEFAULT 'elderly' COMMENT '角色：elderly=老人 family=家属',
  `phone`           VARCHAR(20)   DEFAULT NULL             COMMENT '手机号（选填）',
  `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  INDEX `idx_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ============================================================
-- 3. 家庭关系表 family_relations
-- 记录家属与老人之间的绑定关系，一个家属可绑定多个老人
-- ============================================================
CREATE TABLE `family_relations` (
  `id`              INT           NOT NULL AUTO_INCREMENT  COMMENT '关系ID',
  `family_user_id`  INT           NOT NULL                 COMMENT '家属用户ID',
  `elderly_user_id` INT           NOT NULL                 COMMENT '老人用户ID',
  `relation_name`   VARCHAR(50)   NOT NULL DEFAULT '家属'   COMMENT '关系称谓（儿子/女儿/护工等）',
  `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '绑定时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_family_elderly` (`family_user_id`, `elderly_user_id`),
  INDEX `idx_elderly` (`elderly_user_id`),
  CONSTRAINT `fk_fr_family`  FOREIGN KEY (`family_user_id`)  REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_fr_elderly` FOREIGN KEY (`elderly_user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='家庭关系表';

-- ============================================================
-- 4. 药品表 drugs
-- 存储 OCR 识别后的药品信息，包含原文与简化说明
-- ============================================================
CREATE TABLE `drugs` (
  `id`              INT           NOT NULL AUTO_INCREMENT  COMMENT '药品ID',
  `user_id`         INT           NOT NULL                 COMMENT '所属用户ID（老人）',
  `name`            VARCHAR(200)  NOT NULL                 COMMENT '药品名称',
  `specification`   VARCHAR(200)  DEFAULT NULL             COMMENT '药品规格（如 0.25g*12片）',
  `efficacy`        TEXT          DEFAULT NULL             COMMENT '功效/适应症（原文）',
  `efficacy_simple` TEXT          DEFAULT NULL             COMMENT '功效（通俗简化版）',
  `usage_dosage`    TEXT          DEFAULT NULL             COMMENT '用法用量（原文）',
  `usage_simple`    TEXT          DEFAULT NULL             COMMENT '用法用量（通俗简化版）',
  `frequency`       VARCHAR(100)  DEFAULT NULL             COMMENT '服药频率（如 一日3次）',
  `caution`         TEXT          DEFAULT NULL             COMMENT '注意事项（原文）',
  `caution_simple`  TEXT          DEFAULT NULL             COMMENT '注意事项（通俗简化版）',
  `image_path`      VARCHAR(500)  DEFAULT NULL             COMMENT '药品图片文件名',
  `ocr_raw_text`    TEXT          DEFAULT NULL             COMMENT 'OCR 识别原始文本',
  `notes`           TEXT          DEFAULT NULL             COMMENT '备注（家属/用户手动添加）',
  `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `created_by`      INT           DEFAULT NULL             COMMENT '创建者ID（可能是家属代录）',
  PRIMARY KEY (`id`),
  INDEX `idx_drug_user` (`user_id`),
  INDEX `idx_drug_name` (`name`),
  CONSTRAINT `fk_drug_user`    FOREIGN KEY (`user_id`)    REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_drug_creator` FOREIGN KEY (`created_by`) REFERENCES `users`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='药品信息表';

-- ============================================================
-- 5. 提醒表 reminders
-- 存储定时服药提醒，支持每日/按周重复
-- ============================================================
CREATE TABLE `reminders` (
  `id`              INT           NOT NULL AUTO_INCREMENT  COMMENT '提醒ID',
  `user_id`         INT           NOT NULL                 COMMENT '提醒目标用户ID（老人）',
  `drug_id`         INT           NOT NULL                 COMMENT '关联药品ID',
  `reminder_time`   VARCHAR(10)   NOT NULL                 COMMENT '提醒时间（HH:MM 格式）',
  `dosage`          VARCHAR(100)  DEFAULT NULL             COMMENT '单次剂量（如 每次2片）',
  `meal_relation`   VARCHAR(20)   DEFAULT NULL             COMMENT '饭前饭后：before_meal/after_meal/empty_stomach/before_sleep',
  `repeat_days`     VARCHAR(50)   NOT NULL DEFAULT 'everyday' COMMENT '重复规则：everyday/mon,tue,wed...',
  `status`          VARCHAR(20)   NOT NULL DEFAULT 'active' COMMENT '状态：active/paused/completed',
  `created_by`      INT           DEFAULT NULL             COMMENT '创建者ID（家属代设）',
  `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  INDEX `idx_rem_user` (`user_id`),
  INDEX `idx_rem_drug` (`drug_id`),
  INDEX `idx_rem_status` (`status`),
  INDEX `idx_rem_time` (`reminder_time`),
  CONSTRAINT `fk_rem_user`    FOREIGN KEY (`user_id`)    REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rem_drug`    FOREIGN KEY (`drug_id`)    REFERENCES `drugs`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rem_creator` FOREIGN KEY (`created_by`) REFERENCES `users`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服药提醒表';

-- ============================================================
-- 6. 服药记录表 medication_logs
-- 记录每次服药的实际情况：已服、迟服、漏服、待服
-- ============================================================
CREATE TABLE `medication_logs` (
  `id`              INT           NOT NULL AUTO_INCREMENT  COMMENT '记录ID',
  `user_id`         INT           NOT NULL                 COMMENT '用户ID',
  `reminder_id`     INT           NOT NULL                 COMMENT '关联提醒ID',
  `scheduled_time`  DATETIME      NOT NULL                 COMMENT '计划服药时间',
  `actual_time`     DATETIME      DEFAULT NULL             COMMENT '实际服药时间',
  `status`          VARCHAR(20)   NOT NULL DEFAULT 'pending' COMMENT '状态：taken/missed/late/pending',
  `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  INDEX `idx_log_user` (`user_id`),
  INDEX `idx_log_reminder` (`reminder_id`),
  INDEX `idx_log_scheduled` (`scheduled_time`),
  INDEX `idx_log_status` (`status`),
  CONSTRAINT `fk_log_user`     FOREIGN KEY (`user_id`)     REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_log_reminder` FOREIGN KEY (`reminder_id`) REFERENCES `reminders`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服药记录表';

-- ============================================================
-- 7. 插入演示数据（可选）
-- ============================================================

-- 7.1 创建演示用户
-- 密码均为 123456，bcrypt 加密后的值
-- 密码已使用bcrypt加密
INSERT INTO `users` (`username`, `hashed_password`, `display_name`, `role`, `phone`) VALUES
('laowang',  '$2b$12$cnugdhzPegJ33Ra5fabRfuUYPn.6OAZ9kar5wH9pnr5eKhtiTreOq', '王大爷', 'elderly', '13800138001'),
('laozhang', '$2b$12$cnugdhzPegJ33Ra5fabRfuUYPn.6OAZ9kar5wH9pnr5eKhtiTreOq', '张奶奶', 'elderly', '13800138002'),
('xiaoming', '$2b$12$cnugdhzPegJ33Ra5fabRfuUYPn.6OAZ9kar5wH9pnr5eKhtiTreOq', '小明',   'family',  '13900139001');

-- 7.2 建立家庭关系：小明绑定王大爷和张奶奶
INSERT INTO `family_relations` (`family_user_id`, `elderly_user_id`, `relation_name`) VALUES
(3, 1, '儿子'),
(3, 2, '女婿');

-- 7.3 添加示范药品
INSERT INTO `drugs` (`user_id`, `name`, `specification`, `efficacy`, `efficacy_simple`, `usage_dosage`, `usage_simple`, `frequency`, `caution`, `caution_simple`, `created_by`) VALUES
(1, '阿莫西林胶囊', '0.25g×24粒',
 '适用于敏感菌所致的呼吸道感染、泌尿生殖道感染、皮肤软组织感染等',
 '这个药的作用是：杀菌消炎，治疗嗓子发炎、尿路感染、皮肤感染等',
 '口服。成人一次0.5g，每6-8小时1次，一日剂量不超过4g',
 '用嘴吃（口服），每次吃2粒，每天吃3次（早中晚各一次）。',
 '一日3次',
 '对青霉素过敏者禁用。肝肾功能不全者慎用',
 '注意：对青霉素过敏的人不能吃；肝不好的人要小心；肾不好的人要小心。',
 3),
(1, '硝苯地平控释片', '30mg×7片',
 '用于高血压、冠心病、慢性稳定型心绞痛的治疗',
 '这个药的作用是：降低血压，治疗高血压和心绞痛',
 '口服，不可咀嚼或掰开。一次30mg，一日1次',
 '用嘴吃（口服），每次吃1片，每天吃1次。整片吞下，不要嚼碎。',
 '一日1次',
 '低血压患者禁用。服药后可能出现头痛、面部潮红',
 '注意：血压太低的人不能吃；吃了可能会头疼或脸发红，这是正常的。',
 3),
(2, '二甲双胍缓释片', '0.5g×30片',
 '用于2型糖尿病，配合饮食控制和运动治疗',
 '这个药的作用是：降低血糖，帮助控制糖尿病',
 '口服，随餐服用。起始剂量0.5g，一日一次，晚餐时服用',
 '用嘴吃（口服），每次吃1片，每天吃1次。在吃饭之后吃。',
 '一日1次',
 '肾功能不全、酮症酸中毒患者禁用。服药期间避免饮酒',
 '注意：肾不好的人不能吃；吃这个药的时候不要抽烟喝酒。',
 3);

-- 7.4 添加示范提醒
INSERT INTO `reminders` (`user_id`, `drug_id`, `reminder_time`, `dosage`, `meal_relation`, `repeat_days`, `status`, `created_by`) VALUES
(1, 1, '08:00', '每次2粒', 'after_meal', 'everyday', 'active', 3),
(1, 1, '14:00', '每次2粒', 'after_meal', 'everyday', 'active', 3),
(1, 1, '20:00', '每次2粒', 'after_meal', 'everyday', 'active', 3),
(1, 2, '08:00', '每次1片', 'after_meal', 'everyday', 'active', 3),
(2, 3, '18:30', '每次1片', 'after_meal', 'everyday', 'active', 3);

-- ============================================================
-- 完成！
-- 数据库 medication_reminder 初始化成功
-- 演示账号：
--   老人端：laowang / 123456（王大爷）
--   老人端：laozhang / 123456（张奶奶）
--   家属端：xiaoming / 123456（小明）
-- ============================================================