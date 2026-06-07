CREATE DATABASE IF NOT EXISTS seoul_commercial
LOCATION '/user/maria_dev/seoul-commercial-analysis/warehouse';

USE seoul_commercial;

DROP TABLE IF EXISTS seoul_commercial_master;
CREATE EXTERNAL TABLE seoul_commercial_master (
    `기준_년분기_코드`    STRING,
    `상권_코드`          STRING,
    `서비스_업종_코드_명`  STRING,
    `당월_매출_금액`      BIGINT,
    `당월_매출_건수`      BIGINT,
    `연령대_20_매출_금액`  BIGINT,
    `연령대_30_매출_금액`  BIGINT,
    `점포_수`            BIGINT,
    `개업_점포_수`        BIGINT,
    `폐업_점포_수`        BIGINT,
    `총_유동인구_수`      BIGINT,
    `상권_구분_코드_명`    STRING,
    `상권_코드_명`        STRING,
    `자치구_코드_명`      STRING,
    `행정동_코드_명`      STRING,
    `경도`              DOUBLE,
    `위도`              DOUBLE
)
STORED AS PARQUET
LOCATION '/user/maria_dev/seoul-commercial-analysis/data/processed/master_dataset';

DROP TABLE IF EXISTS seoul_q3_ml_result;
CREATE EXTERNAL TABLE seoul_q3_ml_result (
    `상권_코드`          STRING,
    `상권_코드_명`        STRING,
    `서비스_업종_코드_명`  STRING,
    `MZ_매출_비중`        DOUBLE,
    `상대_시장활력도_비율`  DOUBLE,
    `상권_특화도_LQ`      DOUBLE,
    `상권_경쟁밀도`        DOUBLE,
    `청년안착_적합도`      DOUBLE,
    `진입가능성`          DOUBLE,
    `청년_라이징_추천점수`  DOUBLE
)
STORED AS PARQUET
LOCATION '/user/maria_dev/seoul-commercial-analysis/data/processed/seoul_q3_ml_result';


WITH Q1_1_base AS (
    SELECT
        `자치구_코드_명`, `상권_코드`, `기준_년분기_코드`,
        SUM(`당월_매출_금액`) AS `분기_총매출`,
        MAX(`총_유동인구_수`) AS `분기_최대_유동인구`
    FROM seoul_commercial.seoul_commercial_master
    WHERE `자치구_코드_명` IS NOT NULL AND `자치구_코드_명` != '미상'
    GROUP BY `자치구_코드_명`, `상권_코드`, `기준_년분기_코드`
)
SELECT
    `자치구_코드_명`,
    COUNT(DISTINCT `상권_코드`) AS `보유_상권_수`,
    ROUND(SUM(`분기_총매출`) / 100000000, 1) AS `구_총매출_억원`,
    ROUND(AVG(`분기_최대_유동인구`) / 10000, 1) AS `분기평균_유동인구_만명`
FROM Q1_1_base
GROUP BY `자치구_코드_명`
ORDER BY `구_총매출_억원` DESC;

WITH Q1_2_quarter AS (
    SELECT
        `자치구_코드_명`, `상권_코드`, `기준_년분기_코드`,
        SUM(`당월_매출_금액`) AS `분기_총매출`,
        SUM(`점포_수`)        AS `분기_총점포수`
    FROM seoul_commercial.seoul_commercial_master
    WHERE `자치구_코드_명` IS NOT NULL AND `자치구_코드_명` != '미상'
    GROUP BY `자치구_코드_명`, `상권_코드`, `기준_년분기_코드`
),
Q1_2_agg AS (
    SELECT
        `자치구_코드_명`,
        AVG(`분기_총매출`)   AS `평균_분기매출`,
        AVG(`분기_총점포수`) AS `평균_분기점포수`
    FROM Q1_2_quarter
    GROUP BY `자치구_코드_명`
)
SELECT
    `자치구_코드_명`,
    ROUND(`평균_분기매출` / 100000000, 1)                              AS `상권당_평균분기매출_억원`,
    ROUND(`평균_분기점포수`, 0)                                         AS `상권당_평균점포수`,
    ROUND((`평균_분기매출` / NULLIF(`평균_분기점포수`, 0)) / 100000000, 3) AS `점포당_평균매출_억원`
FROM Q1_2_agg
ORDER BY `점포당_평균매출_억원` DESC;

WITH Base_Stats AS (
    SELECT `자치구_코드_명`, `서비스_업종_코드_명`,
        SUM(`당월_매출_금액`) AS `매출`, SUM(`점포_수`) AS `점포수`
    FROM seoul_commercial.seoul_commercial_master
    WHERE `자치구_코드_명` IS NOT NULL AND `자치구_코드_명` != '미상'
    GROUP BY `자치구_코드_명`, `서비스_업종_코드_명`
),
Gu_Totals AS (
    SELECT `자치구_코드_명`, SUM(`매출`) AS `구_매출`, SUM(`점포수`) AS `구_점포수` FROM Base_Stats GROUP BY `자치구_코드_명`
),
Seoul_Totals AS (
    SELECT `서비스_업종_코드_명`, SUM(`매출`) AS `업종_매출`, SUM(`점포수`) AS `업종_점포수`,
        (SELECT SUM(`매출`) FROM Base_Stats) AS `서울_매출`,
        (SELECT SUM(`점포수`) FROM Base_Stats) AS `서울_점포수`
    FROM Base_Stats GROUP BY `서비스_업종_코드_명`
),
Weighted_LQ AS (
    SELECT
        a.`자치구_코드_명`, a.`서비스_업종_코드_명`,
        (a.`매출` / b.`구_매출`) / (c.`업종_매출` / c.`서울_매출`) AS `Rev_LQ`,
        (a.`점포수` / b.`구_점포수`) / (c.`업종_점포수` / c.`서울_점포수`) AS `Store_LQ`,
        ROW_NUMBER() OVER(PARTITION BY a.`자치구_코드_명` ORDER BY ((a.`매출` / b.`구_매출`) / (c.`업종_매출` / c.`서울_매출`) * 0.7) + ((a.`점포수` / b.`구_점포수`) / (c.`업종_점포수` / c.`서울_점포수`) * 0.3) DESC) AS `rn`
    FROM Base_Stats a
    JOIN Gu_Totals b ON a.`자치구_코드_명` = b.`자치구_코드_명`
    JOIN Seoul_Totals c ON a.`서비스_업종_코드_명` = c.`서비스_업종_코드_명`
)
SELECT `자치구_코드_명`, `서비스_업종_코드_명` AS `랜드마크_업종`,
    ROUND((`Rev_LQ` * 0.7) + (`Store_LQ` * 0.3), 2) AS `종합_특화도_LQ`,
    ROUND(`Rev_LQ`, 2) AS `매출_LQ`, ROUND(`Store_LQ`, 2) AS `점포수_LQ`
FROM Weighted_LQ
WHERE `rn` = 1
ORDER BY `종합_특화도_LQ` DESC;

WITH Q2_quarter AS (
    SELECT
        `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`, `기준_년분기_코드`,
        SUM(`당월_매출_금액`) / NULLIF(SUM(`점포_수`), 0) / 3.0 AS `월_점포당_매출`,
        AVG(`점포_수`) AS `분기_점포수`
    FROM seoul_commercial.seoul_commercial_master
    GROUP BY `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`, `기준_년분기_코드`
),
Q2_pivot AS (
    SELECT
        `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`,
        COUNT(DISTINCT `기준_년분기_코드`) AS `영업_분기수`,
        AVG(`분기_점포수`) AS `평균_점포수`,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20241' THEN `월_점포당_매출` END), 0) AS Q1_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20242' THEN `월_점포당_매출` END), 0) AS Q2_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20243' THEN `월_점포당_매출` END), 0) AS Q3_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20244' THEN `월_점포당_매출` END), 0) AS Q4_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20251' THEN `월_점포당_매출` END), 0) AS Q5_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20252' THEN `월_점포당_매출` END), 0) AS Q6_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20253' THEN `월_점포당_매출` END), 0) AS Q7_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20254' THEN `월_점포당_매출` END), 0) AS Q8_Rev
    FROM Q2_quarter
    GROUP BY `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`
),
Q2_metrics AS (
    SELECT *,
        ((Q1_Rev + Q2_Rev + Q3_Rev + Q4_Rev) / 4.0) AS `전반기_평균`,
        ((Q5_Rev + Q6_Rev + Q7_Rev + Q8_Rev) / 4.0) AS `후반기_평균`,
        (((Q5_Rev + Q6_Rev + Q7_Rev + Q8_Rev) / 4.0) - ((Q1_Rev + Q2_Rev + Q3_Rev + Q4_Rev) / 4.0)) AS `abs_growth`,
        (((Q5_Rev + Q6_Rev + Q7_Rev + Q8_Rev) / 4.0) / NULLIF(((Q1_Rev + Q2_Rev + Q3_Rev + Q4_Rev) / 4.0), 0)) - 1.0 AS `growth_rate`,
        (IF(Q2_Rev > Q1_Rev, 1, 0) + IF(Q3_Rev > Q2_Rev, 1, 0) + IF(Q4_Rev > Q3_Rev, 1, 0) +
         IF(Q5_Rev > Q4_Rev, 1, 0) + IF(Q6_Rev > Q5_Rev, 1, 0) + IF(Q7_Rev > Q6_Rev, 1, 0) +
         IF(Q8_Rev > Q7_Rev, 1, 0)) AS `up_count`
    FROM Q2_pivot
    WHERE `영업_분기수` >= 4
),
Q2_minmax AS (
    SELECT `서비스_업종_코드_명`,
        MIN(`abs_growth`) AS min_vol, MAX(`abs_growth`) AS max_vol,
        MIN(`growth_rate`) AS min_spd, MAX(`growth_rate`) AS max_spd
    FROM Q2_metrics
    WHERE `전반기_평균` > 0 AND `후반기_평균` > 0
    GROUP BY `서비스_업종_코드_명`
    HAVING COUNT(*) >= 3
),
Q2_normalize AS (
    SELECT a.*,
        COALESCE(((a.`abs_growth` - b.min_vol) / NULLIF(b.max_vol - b.min_vol, 0)) * 100, 50) AS norm_vol,
        COALESCE(((a.`growth_rate` - b.min_spd) / NULLIF(b.max_spd - b.min_spd, 0)) * 100, 50) AS norm_spd,
        (a.`up_count` / 7.0) * 100 AS norm_cnt
    FROM Q2_metrics a
    JOIN Q2_minmax b ON a.`서비스_업종_코드_명` = b.`서비스_업종_코드_명`
)
SELECT
    '메가 핫플' AS `구분`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`,
    ROUND(`평균_점포수`, 1) AS `평균_점포수`,
    ROUND(`전반기_평균` / 10000, 0) AS `24년_월점포당_만원`,
    ROUND(`후반기_평균` / 10000, 0) AS `25년_월점포당_만원`,
    ROUND(`growth_rate` * 100, 1)   AS `성장률_퍼센트`,
    `up_count` AS `연속상승_횟수`,
    ROUND((norm_vol * 0.60) + (norm_spd * 0.20) + (norm_cnt * 0.20), 2) AS `메가_상승_총점`
FROM Q2_normalize
WHERE `평균_점포수` >= 30
  AND `전반기_평균` >= 40000000
  AND `growth_rate` > 0
ORDER BY `메가_상승_총점` DESC
LIMIT 10;

WITH Q2_quarter AS (
    SELECT
        `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`, `기준_년분기_코드`,
        SUM(`당월_매출_금액`) / NULLIF(SUM(`점포_수`), 0) / 3.0 AS `월_점포당_매출`,
        AVG(`점포_수`) AS `분기_점포수`
    FROM seoul_commercial.seoul_commercial_master
    GROUP BY `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`, `기준_년분기_코드`
),
Q2_pivot AS (
    SELECT
        `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`,
        COUNT(DISTINCT `기준_년분기_코드`) AS `영업_분기수`,
        AVG(`분기_점포수`) AS `평균_점포수`,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20241' THEN `월_점포당_매출` END), 0) AS Q1_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20242' THEN `월_점포당_매출` END), 0) AS Q2_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20243' THEN `월_점포당_매출` END), 0) AS Q3_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20244' THEN `월_점포당_매출` END), 0) AS Q4_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20251' THEN `월_점포당_매출` END), 0) AS Q5_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20252' THEN `월_점포당_매출` END), 0) AS Q6_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20253' THEN `월_점포당_매출` END), 0) AS Q7_Rev,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20254' THEN `월_점포당_매출` END), 0) AS Q8_Rev
    FROM Q2_quarter
    GROUP BY `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`
),
Q2_metrics AS (
    SELECT *,
        ((Q1_Rev + Q2_Rev + Q3_Rev + Q4_Rev) / 4.0) AS `전반기_평균`,
        ((Q5_Rev + Q6_Rev + Q7_Rev + Q8_Rev) / 4.0) AS `후반기_평균`,
        (((Q5_Rev + Q6_Rev + Q7_Rev + Q8_Rev) / 4.0) / NULLIF(((Q1_Rev + Q2_Rev + Q3_Rev + Q4_Rev) / 4.0), 0)) - 1.0 AS `growth_rate`,
        (IF(Q2_Rev > Q1_Rev, 1, 0) + IF(Q3_Rev > Q2_Rev, 1, 0) + IF(Q4_Rev > Q3_Rev, 1, 0) +
         IF(Q5_Rev > Q4_Rev, 1, 0) + IF(Q6_Rev > Q5_Rev, 1, 0) + IF(Q7_Rev > Q6_Rev, 1, 0) +
         IF(Q8_Rev > Q7_Rev, 1, 0)) AS `up_count`
    FROM Q2_pivot
    WHERE `영업_분기수` >= 4
)
SELECT
    '라이징 핫플' AS `구분`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`,
    ROUND(`평균_점포수`, 1)        AS `평균_점포수`,
    ROUND(`전반기_평균` / 10000, 0) AS `24년_월점포당_만원`,
    ROUND(`후반기_평균` / 10000, 0) AS `25년_월점포당_만원`,
    ROUND(`growth_rate` * 100, 1)  AS `성장률_퍼센트`,
    `up_count`                     AS `연속상승_횟수`
FROM Q2_metrics
WHERE `평균_점포수` >= 15 AND `평균_점포수` < 30
  AND `전반기_평균` >= 20000000 AND `전반기_평균` < 40000000
  AND `growth_rate` >= 0.20
  AND `up_count` >= 2
ORDER BY `growth_rate` DESC
LIMIT 10;
