Tandem 🚲
SJSU Career Mentorship, matched with purpose. Texas Instruments × SJSU Career Center · TI track, SpartHill Hack 2026 (Responsible AI for Business & Society)

Tandem pairs SJSU students with industry mentors for a structured 12-week program (orientation, four guided lessons, closing session), with explainable AI matching, human approval of every match, and engagement tracking for Career Center staff.

1. Quick start
pip install -r requirements.txt
streamlit run app.py        # full app
python demo.py              # matching engine only, prints results in the terminal
Demo data (60 students, 50 mentors) loads automatically on first run into a SQLite database, tandem.db (git-ignored). Admin → Settings → Reset demo data starts over.

Demo logins

Role	Email	Password
Admin	admin@sjsu.edu	admin1234
Staff	staff@sjsu.edu	staff1234
Mentee	student1@sjsu.edu … student60@sjsu.edu	demo1234
Mentor	mentor1@example.com … mentor30@example.com	demo1234
The login page also has a "Quick log in" picker for judges.

Deploy (free): share.streamlit.io → Create app → repo IgorLikesAnime/Tandem, branch main, file app.py → Deploy.

3-minute demo script
Create account as a new student → fill the application → "You're all set" → edit profile.
Log in as Admin → Matching → Run matching → Approve all High confidence.
On a Low confidence match, click Deny.
Reassign another match from its alternatives.
Release matches (simulated emails go out) → Settings → Simulate weeks 1 to 5.
Show Overview (metrics, confidence, fairness), Progress (engagement, at-risk), Insights (mentor supply gap, learned weights).
Log in as a Mentee → see mentor bio + shared times → tick prework → "You're ready to meet your mentor!" → submit a file → send a message → see reminder notifications.
Log in as the Mentor → see the mentee's prework status, submission, and message → check in.
2. Roles and access
Role	Who	Can do
Mentee	SJSU students	Apply, see own match and why, prework/postwork checklists, session check-ins
Mentor	Industry professionals (1+ year experience)	Apply, see own mentees and their prework status, own prep checklist, check-ins
Staff	Career Center coordinators	Run matching, approve/deny/reassign matches with feedback, release matches, view progress, flags, insights, reports
Admin	Career Center lead	Everything Staff can do, plus open/close applications, edit curriculum, reset data
Access is controlled by one PERMISSIONS table in app.py (feature → allowed roles). Every tab and button checks it, and Admin → Settings shows the full matrix. Mentors and mentees only see their own data. Accounts use email + password (PBKDF2-SHA256 salted hashes). Admin can add Staff/Admin accounts in Settings. Production would add SJSU single sign-on.

3. Program flow
Applications open (Admin sets the deadline, e.g. one month) → students and mentors create an account on Tandem, fill the dropdown application, and sign the agreement. They then see "You're all set. We'll email you when you have a match" and get a confirmation email. They can edit their profile any time until the deadline passes or applications are closed; after that the profile is locked for matching.
Applicants are approved automatically and join the matching pool right away (mentors under 1 year of experience can't submit).
Admin closes applications and clicks Run matching (batch, everyone at once).
Staff review matches: approve, deny, reassign, or approve all High confidence. Approved pairs are locked; re-running matching only re-matches the rest.
Staff or Admin releases matches (the button only appears once every student has an approved match) → both sides get an email ("log in to see your match").
12-week program: for each of 6 sessions, mentee does prework → session → both check in → postwork.
Staff track engagement, follow up on flags, and export reports.
4. Data collected
Everything that affects matching is a dropdown or checkbox (no free text), so tags are always clean and both sides use the exact same lists.

Student application
Field	Input	Used for
Full name, SJSU email	Text (must end in @sjsu.edu)	Contact
Major	Dropdown	Matching: background (10 pts)
Minor	Dropdown	Matching: background (partial credit)
Year	Dropdown	Filter (if the mentor chose preferred years) + fairness check
College (e.g. College of Engineering)	Dropdown	Reporting
Profile picture	Upload	Shown to matched mentor only
Industry of interest	Dropdown	Matching: industry (30 pts)
Goals, ranked #1 / #2 / #3	3 dropdowns (no repeats)	Matching: goals (50 pts)
Availability	Day × time grid (21 slots)	Hard filter + matching (10 pts)
Meeting preference	Dropdown	Hard filter
About me	Short text	Display only: shown to the matched mentor. Never used for matching
Mentee agreement	Checkbox (timestamped)	Required
Mentor application
Field	Input	Used for
Full name, email, company, job title	Text	Profile
Years of work experience	Dropdown	Eligibility: under 1 year is blocked
Industry they work in	Dropdown	Matching: industry
College + degree major	Dropdowns	Matching: background (major, or same college for partial credit)
Degree minor	Dropdown	Matching: background
School	Dropdown	Profile shown to mentee
Other connection to SJSU (only asked if the school is not SJSU; SJSU graduates count as alum)	Dropdown	Background points (SJSU connection) + match reason
Students they advise best (class years)	Multi-select	Hard filter: only those years are matched
Student goals you can help with	Multi-select	Matching: goals
Profile picture	Upload	Shown to matched mentees only
Availability	Day × time grid (21 slots)	Hard filter + matching
Meeting preference	Dropdown	Hard filter
Max mentees (1, 2 or 3)	Dropdown	Capacity
Short bio + LinkedIn	Text	Display only: shown to matched mentees. Never used for matching
Mentor agreement	Checkbox (timestamped)	Required
A mentor's degree and industry can differ (e.g. EE degree, Sales/Business industry); they are scored separately.

Not collected on purpose: gender, race, ethnicity, age, photos, or any other demographic data. These are never used in matching.

Dropdown options (matching.py)
Industry (10): Semiconductors/Hardware, Embedded Systems, Software, AI/ML/Data, Product Management, Sales/Business, Consulting, Finance, Healthcare/Biotech, Design/UX
Goals (10): Resume Review, LinkedIn/Branding, Behavioral Interviews, Technical Interviews, Networking, Internship Search, Job Search Strategy, Career Exploration, Grad School Advice, Industry Insights
Major (8): EE, CMPE, CS, ME, Business, Data Science, Other Engineering, Other
Minor (11): None, EE, CMPE, CS, ME, Business, Data Science, Math, Psychology, Communications, Other
Year: Freshman, Sophomore, Junior, Senior, Masters, PhD
Availability: Mon to Sun × Morning (8-12) / Afternoon (12-5) / Evening (5-9), Pacific time
Meeting preference: In person, Virtual, Either
Experience: 1-2, 3-5, 6-10, 10+
Admins can add options by editing these lists in matching.py.

5. Matching algorithm (matching.py)
Step 1: Hard filters (pair excluded if any fail)
Mentor has 1+ year of experience and is approved
At least one shared day × time slot
Meeting modes compatible ("Either" matches anything)
Staff has not previously denied this exact pair
Student's year is one the mentor said they can advise (if the mentor picked any)
Strong-match threshold (Admin setting, default 50%): every student still gets their closest available mentor, but matches below the threshold are flagged to staff as "⚠️ No strong match found, closest available mentor shown". Staff decide. Nobody is silently dropped, and nobody is quietly given a weak match.

Step 2: Score each pair (0 to 100)
Factor	Points	Rule
Goal #1 covered	25	Mentor's "goals you can help with" includes it
Goal #2 covered	15	
Goal #3 covered	10	
Industry	30	Same industry = full. Related = partial (Semiconductors↔Embedded 60%, Software↔AI/ML 60%, Sales↔Consulting 50%, PM↔Design 50%, Embedded↔Software 40%, PM↔Software 40%, Finance↔Consulting 40%)
Background (major/minor + SJSU connection)	10	60% major/minor/college (same major = full, via minor = 60%, same college only = 30%) + 40% SJSU connection (adjunct/lecturer = full, involved alum = 75%, alum = 50%, none = 0)
Availability	10	3+ shared slots = 10, 2 = 6.7, 1 = 3.3
Goals carry the most weight because they are what the student explicitly asked for, in their own priority order.

Step 3: Assign (Hungarian algorithm)
The score is the recommender (ranks mentors per student). The Hungarian algorithm is the assigner: it uses the same scores, no extra weights, and picks the pairing with the highest total for everyone. Example: Student A scores Mentor 1 = 98, Mentor 2 = 94; Student B scores Mentor 1 = 95, Mentor 2 = 60. Greedy gives A→M1, B→M2 (total 158). Hungarian gives A→M2, B→M1 (total 189): A still gets a great mentor and B isn't stuck with a poor one.

scipy.optimize.linear_sum_assignment finds the pairing with the highest total score across everyone, not just the best for whoever is processed first. Capacity: a mentor who takes 3 mentees becomes 3 slots, so 1:1 and 1:many use the same code. Locked (approved) pairs keep their slots; denied pairs are excluded.

Step 4: Confidence
Level	Rule
🟢 High	Score ≥ 75 and at least 10 points ahead of this student's next-best mentor
🟡 Medium	Everything in between
🔴 Low	Score < 55 (listed first for staff review)
Step 5: Explanation
Every match shows a plain-language reason, e.g. "covers #1 Resume Review, #2 Networking; same industry (Software); shared background via minor (Business); both free Tue Evening, Sat Morning", plus gaps (what the mentor doesn't cover) and per-factor score bars.

Unmatched students
Reported with the reason, framed as a gap in the mentor pool, not the student: "9 compatible mentors, all at capacity. Recruit more mentors in Software."

6. Feedback loop: learning for next time (extra credit)
Text feedback is used too (VADER sentiment analysis + keyword rules; no LLM, runs offline, free, explainable):

Session feedback text → sentiment score (-1 to +1). Session quality = 70% star rating + 30% sentiment.
Safety words ("rude", "never showed", "uncomfortable"...) → flag for a human. Never auto-actioned.
Two learners, used in sequence (cold start → ML):

Rule-based	ML model
When	Always (first cycle)	Once 30+ labeled pairs with both outcomes exist
How	Approved vs denied factor averages	Logistic regression: P(match succeeds) from the 4 factor scores
Output	Suggested weights	Suggested weights (from coefficients) + cross-validated accuracy + predicted success % on match cards
Staff feedback is a checklist, not just free text, so the algorithm can use it.

Signal	Source	Effect
Approve	Staff approves a match	Positive example
Deny	Staff denies a match	Negative example
Reassign	Staff picks another mentor	Negative example for the original pair
Session outcome	Check-in surveys	Pair averaging under 3/5, or saying "don't continue", counts as unsuccessful
learn_weights() compares how each factor scored in successful vs unsuccessful pairs, and rescales to 100. Admin sees current vs suggested weights in Insights and clicks Apply (a human approves the change). The next matching run uses the new weights.

7. Program tools
Curriculum (editable by Admin): Orientation (week 1), Lesson 1 Career Goals (3), Lesson 2 Resume & LinkedIn (5), Lesson 3 Networking & Interviews (7), Lesson 4 Internship & Job Strategy (9), Closing (12). Each has mentee prework, mentor prep, and postwork checklists.

Prework: mentee ticks items → "You're ready to meet your mentor.". Mentor sees "✅ Priya has finished prework (3/3)" or "⏳ 1/3 done".

Before each session (both sides): confirm attendance or ask to reschedule, with an optional note.

After each session (both sides): Did it happen? (Yes/No/Rescheduled), on time?, usefulness 1-5, continue with this match?, optional written feedback (scored for sentiment). Both Yes → Attended · both No → Missed · disagree → ⚠️ Flagged for staff.

Submissions: mentee submits prework/postwork as notes, a link, or a file (PDF/DOCX/PNG/JPG/TXT, up to 5 MB); the mentor can view and download it.

Messaging: private thread per mentor-mentee pair (not visible to staff).

Automated reminders tied to the program calendar (Admin sets the start date): prework due (2 days before a session), session tomorrow (1 day before), check-in missing (day after), postwork pending (3 days after). Each fires once, shows up as an in-app notification, and is logged as an email. Admin has a demo clock to fast-forward.

Talking points for mentors: each session shows platform guidance built from the curriculum and the mentee's own #1-#3 goals (e.g. "#1 goal, Resume Review: go through their resume and agree on 2 edits").

Mentor notified when the mentee finishes prework. Mentor feedback also records which of the mentee's goals they covered (yes/no per tag).

Announcements: Staff send mass emails (e.g. orientation details) to everyone, mentees, mentors, or matched pairs only.

Lesson plans importable: Admin downloads the curriculum as a CSV template, edits it, and imports it.

Emails: application confirmation, match release, reminders (simulated, logged in Reports).

Session booking (idea from Henry's prototype): either side books each session on a day + time slot inside that session's week, chosen only from slots both marked as free. The app blocks double-booking a mentor and emails both people. Reminders follow the booked date.

Scorecards (super-admin only)
Every mentor and mentee gets a score and grade from their sessions: 30% attendance + 20% preparation (prework or mentor prep) + 15% confirming and giving feedback + 35% how their partner rated sessions (80% stars, 20% written-feedback sentiment). Grades: A 85+, B 70+, C 55+, D below. Used for coaching and recognition (e.g. top mentor), never shown to participants.

Dashboards
Who	Tabs
Mentee	Home (status or mentor card with bio, shared times, why matched, next session) · Sessions · Messages · My profile
Mentor	Home (mentee list + progress) · one tab per mentee (profile, Sessions, Messages) · My profile
Staff	Overview · Applications (search + filters + export) · Matching · Progress · Flags · Scorecards · Insights · Users · Reports (Excel/CSV)
Admin	Staff tabs + Settings (calendar, curriculum, dropdown options, new cycle + archive, permissions matrix, add staff, demo tools)
Admin never touches the database. Users tab: search, edit name, change role (Admin only), deactivate, reset password. Settings: open/close applications, start a new cycle (old one is archived), edit dropdown options, re-run matching for late applicants.

8. Metrics (Staff/Admin dashboard)
Overview: approved students/mentors, % matched, avg score, mentor slots, session completion, on-time %, avg rating, avg prework done, at-risk pairs, confidence breakdown, fairness table (match rate and score by major and year).
Progress: per-pair engagement score = 50% attendance + 30% prework + 20% ratings. At risk = missed or disputed session, prework under 50%, or rating under 3.
Insights: mentor supply gap (students wanting X vs mentor slots for X, coverage %, "recruit more" alerts), feedback learning.
Reports: CSV export of matches + engagement, students, mentors; satisfaction by session; email log.
9. Responsible AI
No demographic data collected or used. Only career tags the person chose.
Explainable: every score is broken down by factor with a written reason and gaps.
Human in the loop: AI proposes, staff approve. Weight changes also need approval.
Fairness check: match rate and score by major and year, so no group is left behind.
Respectful framing: a low score means "our mentor pool doesn't cover this yet", never "this student is a bad fit".
Least privilege: mentors and mentees only see their own data.
10. Project structure
File	What it does
app.py	Streamlit app: accounts, applications, dashboards, messaging, submissions, reminders
matching.py	Dropdown lists, filters, scoring, assignment, confidence, explanations, supply gap, learning
seed_data.py	Generates realistic fake students and mentors
demo.py	Runs the matching pipeline in the terminal
requirements.txt	numpy, scipy, pandas, streamlit, scikit-learn, vaderSentiment
11. Handshake "Mentorship Platform Intern" requirements
Requirement (SJSU × TI posting)	Tandem
Applicant intake and eligibility review	✅ Accounts, applications, agreements, 1-year mentor rule, staff approve/reject
Mentor-mentee matching based on program criteria	✅ Explainable scoring + Hungarian assignment + human approval
Attendance tracking and prework/postwork submissions per session	✅ Two-sided check-ins, checklists, file/link submissions
Messaging between matched pairs	✅ Private per-pair threads
Automated reminders tied to the program schedule	✅ Calendar-driven, fire once each
Feedback collection and reporting dashboard	✅ Surveys, engagement, satisfaction, CSV export
Databases and user authentication	✅ SQLite + salted password hashing, role-based access
12. Status
Done ✅

Student and mentor applications (dropdowns, ranked goals, major + minor, day × time slots, agreements)
1-year mentor experience rule
Matching: filters, weighted scoring, Hungarian assignment, capacity, confidence, explanations
Staff/Admin roles; applicants auto-approved; approve/deny/reassign/lock; re-run
Close applications → release matches with emails
Prework, mentor prep, postwork checklists; session check-ins; disagreement flags
Metrics, fairness check, engagement score, at-risk pairs, supply gap, CSV export
Feedback learning from staff decisions and session outcomes
Accounts (email + password), "You're all set" confirmation, profile editing until the deadline
Display-only bios, private messaging, prework/postwork submissions, automated reminders
Next ⏳

Send real emails (SMTP or SendGrid) instead of the simulated log
SJSU single sign-on and a hosted database such as Postgres (needed for the Spring rollout)
Password reset and email verification
Calendar scheduling of sessions within shared slots
Optional NFC/QR check-in for in-person sessions
Optional free-text goals + embeddings for richer matching
