Here's a structured test list covering every feature, grouped by component:

Scraper
#	Edge Case	Command	Expected
S1	Duplicate jobs across keywords	--scrape twice	Second run inserts 0 new rows
S2	Job with empty description	Check DB after scrape	description = "" stored, doesn't crash pipeline
S3	Scrape with a keyword that returns 0 results	Temporarily add "quantum photonics engineer" to JOB_SEARCH["keywords"]	Prints "No results", continues
Classifier
#	Edge Case	Command	Expected
C1	LinkedIn Easy Apply job	--classify on a known LinkedIn job	easy
C2	FAANG job (Google, Apple, Amazon)	Check classified rows	full_form (their own portals)
C3	Job with null apply_url	Insert a dummy row with no URL	unknown, no crash
C4	Re-run --classify	--classify again	"No unclassified jobs" — doesn't re-classify already-done rows
AI Pipeline
#	Edge Case	Command	Expected
A1	Job below fit threshold (score < 65)	Find a low-fit job or lower FIT_SCORE_THRESHOLD to 80 temporarily	Skipped with "Fit score X below threshold"
A2	ATS check fails but fixes on retry	Process a job where Mistral produces >20 bullets	Loop retries, fixes, saves
A3	Resume quality below RESUME_SIMILARITY_MIN (70)	Lower threshold to 95 temporarily	Job marked status=2 "Resume quality too low"
A4	(Action Verb: X) tags cleaned	Check any newly generated .txt file	No (Action Verb: strings in output
A5	Ollama not running	Stop Ollama, run --process --limit 1	Fails with a clear error, not a silent hang
A6	Job description truncated at 2000 chars	Find a job with a very long JD	Processes fine, doesn't crash
PDF / LaTeX
#	Edge Case	Command	Expected
P1	Special chars in company name (S&P Global, AT&T)	Check generated .tex	S\&P Global — escaped correctly
P2	Resume spills to 2 pages	Run generate_tex.py --compile on a verbose resume	Compression triggers, PDF is 1 page
P3	Missing section (no certifications)	Edit a .txt to remove the certs block, re-run generate_tex.py	PDF generates cleanly without a blank section
P4	Summary section present in PDF	Open any generated PDF	Summary is the first section after contact info
ATS Checker (check_resume.py)
#	Edge Case	Command	Expected
R1	Exactly 20 bullets	python check_resume.py <path>	✅ passes bullet count
R2	21 bullets	Manually add a bullet, re-check	❌ fails bullet count
R3	Zero quantified bullets	Strip all numbers from a resume copy	❌ fails quantification
R4	Repeated action verb	Duplicate a bullet's first word	❌ flags overused verb
R5	Mixed date formats	Change one date to "Jan 2024" in a resume that uses "January"	❌ flags inconsistent dates
DB / Deduplication
#	Edge Case	Command	Expected
D1	--scrape twice in a row	Run twice	Row count stays the same on second run
D2	--process on already-processed jobs	Run --process with no new jobs	"No new jobs to process."
D3	Two pipeline instances at once	Open two terminals, run simultaneously	Second exits: "Pipeline already running (PID …)"
D4	Stale lock file (from a crash)	echo 99999 > output/pipeline.lock, then run	Detects dead PID, removes stale lock, continues
Dashboard API
#	Edge Case	Command	Expected
W1	/api/stats returns correct counts	curl localhost:8765/api/stats	JSON with total, applied, easy_apply etc.
W2	/api/jobs/<id> for valid ID	curl localhost:8765/api/jobs/<job_id>	Full job JSON
W3	/api/jobs/<id> for invalid ID	curl localhost:8765/api/jobs/fake_id	{"error": "not found"} with 404
W4	Frontend filter by easy apply type	Open dashboard, filter dropdown	Table shows only easy-apply jobs
W5	Frontend search	Type "Amazon" in search box	Only Amazon rows show
W6	Sort by fit score descending	Click "Fit" column header	Highest scores at top
Cron Safety
#	Edge Case	Command	Expected
CR1	Wrong AI mode + missing key	AI_MODE=groq python main.py with no GROQ_API_KEY	Exits immediately with clear error message
CR2	Run log written	Check output/run.log after any run	Timestamps + "Pipeline started/finished" entries
CR3	--limit respected	--process --limit 2	Exactly 2 jobs processed, no more
That's 30 cases total. I'd suggest starting with D3 (concurrent lock), A5 (Ollama down), P1 (special chars in LaTeX), and R5 (mixed dates) — those are the ones most likely to surface real bugs. Want me to run any of them for you, or walk through a specific group?