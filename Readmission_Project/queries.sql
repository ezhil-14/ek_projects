
--name: q1_overview
--Query 1: Overview

SELECT 
	COUNT(DISTINCT facility_id) 				AS hospitals,
	COUNT(*) 									AS hospital_condition_rows,
	SUM(has_ratio) 								AS rows_with_ratio,
	ROUND(100.0 * SUM(has_ratio) / COUNT(*), 1) AS pct_rows_with_ratio,
	ROUND(AVG(excess_readmission_ratio), 3) 	AS avg_ratio,
	ROUND(100 * AVG(above_expected), 1) 		AS pct_above_expected,
	MIN(start_date) 							AS period_start,
	MAX(end_date)								AS period_end
	FROM readmissions;	

--name: q2_condition
--Query 2: By condition

SELECT 
	Condition,
	COUNT(*) 								AS hospitals_reported,
	ROUND(AVG(predicted_readmission_rate), 2) 	AS avg_readmission_rate_pct,
	ROUND(AVG(excess_readmission_ratio), 3)	AS avg_ratio,
	ROUND(100.0 * AVG(above_expected), 1)	AS pct_above_expected,
	ROUND(MAX(excess_readmission_ratio), 3)	AS worst_ratio
FROM readmissions
WHERE has_ratio = 1
GROUP BY condition
ORDER BY avg_readmission_rate_pct DESC;

--name: q3_state_rank
--Query 3: State ranking

SELECT
	RANK() OVER (ORDER BY AVG(excess_readmission_ratio) DESC)	AS rank_worst_first, 
	state,
	COUNT(DISTINCT facility_id) 							AS hospitals,
	COUNT(*) 												AS rows_with_ratio,
	ROUND(AVG(excess_readmission_ratio), 3)					AS avg_ratio,
	ROUND(100.0 * AVG(above_expected), 1) 					AS pct_above_expected
FROM readmissions
WHERE has_ratio = 1
GROUP BY state
HAVING COUNT(DISTINCT facility_id) >= 10
ORDER BY rank_worst_first;

--name: q3b_AL_rank
--Query 3b: Alabama's rank

WITH state_ranks AS(
		SELECT
			RANK() OVER (ORDER BY AVG(excess_readmission_ratio) DESC) AS rank_worst_first,
			state,
			COUNT(DISTINCT facility_id)								  AS hospitals,
			ROUND(AVG(excess_readmission_ratio), 3)					  AS avg_ratio
		FROM readmissions
		WHERE has_ratio = 1
		GROUP BY state 
		HAVING COUNT(DISTINCT facility_id) >= 10
)
SELECT *
FROM state_ranks
WHERE state = 'AL';
		
--name: q4_AL_vs_Nation
-- Query 4: Alabama vs national
		
WITH al AS(
	SELECT 
		condition,
		COUNT(*) 						AS al_hospitals,
		AVG(excess_readmission_ratio) 	AS al_avg_ratio,
		AVG(above_expected)				AS al_share_above
	FROM readmissions
	WHERE has_ratio = 1 AND state = 'AL'
	GROUP BY condition
),
US AS (
	SELECT
		condition,
		COUNT(*)						AS us_hospitals,
		AVG(excess_readmission_ratio)	AS us_avg_ratio,
		AVG(above_expected)				AS us_share_above
	FROM readmissions
	WHERE has_ratio = 1
	GROUP BY condition
)
SELECT 
	us.condition,
	al.al_hospitals,
	ROUND(al.al_avg_ratio, 3)					AS al_avg_ratio,
	ROUND(us.us_avg_ratio, 3)					AS us_avg_ratio,
	ROUND(al.al_avg_ratio - us.us_avg_ratio, 3) AS ratio_gap,
	ROUND(100.0 * al.al_share_above, 1) 		AS al_pct_above,
	ROUND(100.0 * us.us_share_above, 1) 		AS us_pct_above
FROM us
LEFT JOIN al ON al.condition = us.condition
ORDER BY ratio_gap DESC;

--name: q5_ownership
-- Query 5: By ownership

SELECT 
	ownership_group,
	COUNT(DISTINCT facility_id) 				AS hospitals,
	COUNT(*)									AS rows_with_ratio,
	ROUND(AVG(excess_readmission_ratio), 3) 	AS avg_ratio,
	ROUND(100* AVG(above_expected), 1)			AS pct_above_expected
FROM readmissions
WHERE has_ratio = 1
	AND ownership_group IS NOT NULL
GROUP BY ownership_group
ORDER BY avg_ratio DESC;

--name: q6_star_rating
-- Query 6: By star rating

SELECT 
	CAST(star_rating AS INTEGER)				AS star_rating,
	COUNT(DISTINCT facility_id)					AS hospitals,
	ROUND(AVG(excess_readmission_ratio), 3)		AS avg_ratio,
	ROUND(100.0* AVG(above_expected), 1)		AS pct_above_expected
FROM readmissions
WHERE has_ratio = 1
	AND star_rating IS NOT NULL
GROUP BY CAST(star_rating AS INTEGER)
ORDER BY star_rating;

--name: q6b_states_ranked
-- Query 6b: Number of states ranked

SELECT COUNT(*) AS total_states
FROM (
	SELECT state
	FROM readmissions
	WHERE has_ratio = 1
	GROUP BY state
	HAVING COUNT(DISTINCT facility_id) >= 10
)AS s;

--name: q07_hospital_summary
-- Query 7: Hospital summary

WITH ranked AS(
	SELECT
		facility_id,
		facility_name,
		city,
		state,
		ownership_group,
		star_rating,
		condition,
		excess_readmission_ratio,
		ROW_NUMBER() 						OVER (PARTITION BY facility_id ORDER BY excess_readmission_ratio DESC) AS rn,
		COUNT(*) 							OVER(PARTITION BY facility_id) 			AS condition_reported,
		SUM(above_expected)					OVER(PARTITION BY facility_id) 			AS condition_above_expected,
		AVG(excess_readmission_ratio) 		OVER(PARTITION BY facility_id) 			AS avg_ratio
	FROM readmissions
	WHERE has_ratio = 1
)
SELECT 
	facility_id,
	facility_name,
	city,
	state,
	ownership_group,
	CAST(star_rating AS INTEGER) 				AS star_rating,
	condition_reported,
	CAST(condition_above_expected AS INTEGER)	AS condition_above_expected,
	ROUND(avg_ratio, 3)							AS avg_ratio,
	condition									AS worst_condition,
	ROUND(excess_readmission_ratio, 3) 			AS worst_ratio
FROM ranked
WHERE rn = 1
ORDER BY avg_ratio DESC;


