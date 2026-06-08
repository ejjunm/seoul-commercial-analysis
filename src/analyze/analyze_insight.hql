-- Q1-1: 자치구별 규모 (총매출·상권수·유동인구)
WITH Q1_1_base AS (
    SELECT
        `자치구_코드_명`, `상권_코드`, `기준_년분기_코드`,
        SUM(`당월_매출_금액`) AS `분기_총매출`,
        MAX(`총_유동인구_수`) AS `분기_최대_유동인구`
    FROM seoul_commercial_master
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

-- Q1-2: 자치구별 실속 (점포당 매출)
WITH Q1_2_quarter AS (
    SELECT
        `자치구_코드_명`, `상권_코드`, `기준_년분기_코드`,
        SUM(`당월_매출_금액`) AS `분기_총매출`,
        SUM(`점포_수`)        AS `분기_총점포수`
    FROM seoul_commercial_master
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
    ROUND(`평균_분기매출` / 100000000, 1)                                         AS `상권당_평균분기매출_억원`,
    ROUND(`평균_분기점포수`, 0)                                                    AS `상권당_평균점포수`,
    ROUND((`평균_분기매출` / NULLIF(`평균_분기점포수`, 0)) / 100000000, 3)          AS `점포당_평균매출_억원`
FROM Q1_2_agg
ORDER BY `점포당_평균매출_억원` DESC;

-- Q1-3: 자치구별 랜드마크 업종 LQ
WITH Base_Stats AS (
    SELECT `자치구_코드_명`, `서비스_업종_코드_명`,
        SUM(`당월_매출_금액`) AS `매출`, SUM(`점포_수`) AS `점포수`
    FROM seoul_commercial_master
    WHERE `자치구_코드_명` IS NOT NULL AND `자치구_코드_명` != '미상'
    GROUP BY `자치구_코드_명`, `서비스_업종_코드_명`
),
Gu_Totals AS (
    SELECT `자치구_코드_명`, SUM(`매출`) AS `구_매출`, SUM(`점포수`) AS `구_점포수`
    FROM Base_Stats GROUP BY `자치구_코드_명`
),
Seoul_Totals AS (
    SELECT `서비스_업종_코드_명`,
        SUM(`매출`) AS `업종_매출`, SUM(`점포수`) AS `업종_점포수`,
        (SELECT SUM(`매출`) FROM Base_Stats) AS `서울_매출`,
        (SELECT SUM(`점포수`) FROM Base_Stats) AS `서울_점포수`
    FROM Base_Stats GROUP BY `서비스_업종_코드_명`
),
Weighted_LQ AS (
    SELECT
        a.`자치구_코드_명`, a.`서비스_업종_코드_명`,
        (a.`매출` / b.`구_매출`) / (c.`업종_매출` / c.`서울_매출`) AS `Rev_LQ`,
        (a.`점포수` / b.`구_점포수`) / (c.`업종_점포수` / c.`서울_점포수`) AS `Store_LQ`,
        ROW_NUMBER() OVER (
            PARTITION BY a.`자치구_코드_명`
            ORDER BY ((a.`매출` / b.`구_매출`) / (c.`업종_매출` / c.`서울_매출`) * 0.7)
                   + ((a.`점포수` / b.`구_점포수`) / (c.`업종_점포수` / c.`서울_점포수`) * 0.3) DESC
        ) AS `rn`
    FROM Base_Stats a
    JOIN Gu_Totals b ON a.`자치구_코드_명` = b.`자치구_코드_명`
    JOIN Seoul_Totals c ON a.`서비스_업종_코드_명` = c.`서비스_업종_코드_명`
)
SELECT
    `자치구_코드_명`,
    `서비스_업종_코드_명` AS `랜드마크_업종`,
    ROUND((`Rev_LQ` * 0.7) + (`Store_LQ` * 0.3), 2) AS `종합_특화도_LQ`,
    ROUND(`Rev_LQ`, 2) AS `매출_LQ`,
    ROUND(`Store_LQ`, 2) AS `점포수_LQ`
FROM Weighted_LQ
WHERE `rn` = 1
ORDER BY `종합_특화도_LQ` DESC;

-- Q2-1: 메가 핫플
WITH Q2_quarter AS (
    SELECT
        `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`, `기준_년분기_코드`,
        SUM(`당월_매출_금액`) / NULLIF(SUM(`점포_수`), 0) / 3.0 AS `월_점포당_매출`,
        AVG(`점포_수`) AS `분기_점포수`
    FROM seoul_commercial_master
    GROUP BY `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`, `기준_년분기_코드`
),
Q2_pivot AS (
    SELECT
        `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`,
        COUNT(DISTINCT `기준_년분기_코드`) AS `영업_분기수`,
        AVG(`분기_점포수`) AS `평균_점포수`,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20241' THEN `월_점포당_매출` END), 0) AS Q1,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20242' THEN `월_점포당_매출` END), 0) AS Q2,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20243' THEN `월_점포당_매출` END), 0) AS Q3,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20244' THEN `월_점포당_매출` END), 0) AS Q4,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20251' THEN `월_점포당_매출` END), 0) AS Q5,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20252' THEN `월_점포당_매출` END), 0) AS Q6,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20253' THEN `월_점포당_매출` END), 0) AS Q7,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20254' THEN `월_점포당_매출` END), 0) AS Q8
    FROM Q2_quarter
    GROUP BY `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`
),
Q2_metrics AS (
    SELECT *,
        (Q1+Q2+Q3+Q4)/4.0 AS `전반기_평균`,
        (Q5+Q6+Q7+Q8)/4.0 AS `후반기_평균`,
        (Q5+Q6+Q7+Q8)/4.0 - (Q1+Q2+Q3+Q4)/4.0 AS `abs_growth`,
        ((Q5+Q6+Q7+Q8)/4.0) / NULLIF((Q1+Q2+Q3+Q4)/4.0, 0) - 1.0 AS `growth_rate`,
        (IF(Q2>Q1,1,0)+IF(Q3>Q2,1,0)+IF(Q4>Q3,1,0)+IF(Q5>Q4,1,0)+
         IF(Q6>Q5,1,0)+IF(Q7>Q6,1,0)+IF(Q8>Q7,1,0)) AS `up_count`
    FROM Q2_pivot WHERE `영업_분기수` >= 4
),
Q2_mega AS (
    SELECT * FROM Q2_metrics
    WHERE `평균_점포수` >= 30 AND `전반기_평균` >= 40000000 AND `growth_rate` > 0
),
Q2_mega_norm AS (
    SELECT *,
        MIN(`abs_growth`)  OVER (PARTITION BY `서비스_업종_코드_명`) AS `min_vol`,
        MAX(`abs_growth`)  OVER (PARTITION BY `서비스_업종_코드_명`) AS `max_vol`,
        MIN(`growth_rate`) OVER (PARTITION BY `서비스_업종_코드_명`) AS `min_spd`,
        MAX(`growth_rate`) OVER (PARTITION BY `서비스_업종_코드_명`) AS `max_spd`
    FROM Q2_mega
)
SELECT
    `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`,
    ROUND(`평균_점포수`, 1)       AS `평균_점포수`,
    ROUND(`전반기_평균`/10000, 0) AS `24년_월점포당_만원`,
    ROUND(`후반기_평균`/10000, 0) AS `25년_월점포당_만원`,
    ROUND(`growth_rate`*100, 1)  AS `성장률_퍼센트`,
    `up_count`                   AS `연속상승_횟수`,
    ROUND(
        (CASE WHEN `max_vol` != `min_vol`
              THEN (`abs_growth`-`min_vol`)/(`max_vol`-`min_vol`)*100 ELSE 50.0 END) * 0.6
      + (CASE WHEN `max_spd` != `min_spd`
              THEN (`growth_rate`-`min_spd`)/(`max_spd`-`min_spd`)*100 ELSE 50.0 END) * 0.2
      + (`up_count`/7.0*100) * 0.2
    , 2) AS `메가_상승_총점`
FROM Q2_mega_norm
ORDER BY `메가_상승_총점` DESC
LIMIT 10;

-- Q2-2: 라이징 핫플
WITH Q2_quarter AS (
    SELECT
        `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`, `기준_년분기_코드`,
        SUM(`당월_매출_금액`) / NULLIF(SUM(`점포_수`), 0) / 3.0 AS `월_점포당_매출`,
        AVG(`점포_수`) AS `분기_점포수`
    FROM seoul_commercial_master
    GROUP BY `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`, `기준_년분기_코드`
),
Q2_pivot AS (
    SELECT
        `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`,
        COUNT(DISTINCT `기준_년분기_코드`) AS `영업_분기수`,
        AVG(`분기_점포수`) AS `평균_점포수`,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20241' THEN `월_점포당_매출` END), 0) AS Q1,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20242' THEN `월_점포당_매출` END), 0) AS Q2,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20243' THEN `월_점포당_매출` END), 0) AS Q3,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20244' THEN `월_점포당_매출` END), 0) AS Q4,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20251' THEN `월_점포당_매출` END), 0) AS Q5,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20252' THEN `월_점포당_매출` END), 0) AS Q6,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20253' THEN `월_점포당_매출` END), 0) AS Q7,
        COALESCE(MAX(CASE WHEN `기준_년분기_코드` = '20254' THEN `월_점포당_매출` END), 0) AS Q8
    FROM Q2_quarter
    GROUP BY `상권_코드`, `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`
),
Q2_metrics AS (
    SELECT *,
        (Q1+Q2+Q3+Q4)/4.0 AS `전반기_평균`,
        (Q5+Q6+Q7+Q8)/4.0 AS `후반기_평균`,
        ((Q5+Q6+Q7+Q8)/4.0) / NULLIF((Q1+Q2+Q3+Q4)/4.0, 0) - 1.0 AS `growth_rate`,
        (IF(Q2>Q1,1,0)+IF(Q3>Q2,1,0)+IF(Q4>Q3,1,0)+IF(Q5>Q4,1,0)+
         IF(Q6>Q5,1,0)+IF(Q7>Q6,1,0)+IF(Q8>Q7,1,0)) AS `up_count`
    FROM Q2_pivot WHERE `영업_분기수` >= 4
)
SELECT
    `상권_코드_명`, `자치구_코드_명`, `서비스_업종_코드_명`,
    ROUND(`평균_점포수`, 1)        AS `평균_점포수`,
    ROUND(`전반기_평균`/10000, 0)  AS `24년_월점포당_만원`,
    ROUND(`후반기_평균`/10000, 0)  AS `25년_월점포당_만원`,
    ROUND(`growth_rate`*100, 1)   AS `성장률_퍼센트`,
    `up_count`                    AS `연속상승_횟수`
FROM Q2_metrics
WHERE `평균_점포수` >= 15 AND `평균_점포수` < 30
  AND `전반기_평균` >= 20000000 AND `전반기_평균` < 40000000
  AND `growth_rate` >= 0.20
  AND `up_count` >= 3
ORDER BY `growth_rate` DESC
LIMIT 10;
