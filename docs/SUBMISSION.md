# Submission kit (Phase 7)

Hard deadline: Dec 4 2026, 2:00 PM PT (Dec 5, 3:30 AM IST). Target: submit Dec 3. After the deadline nothing can be edited.

## Assets to produce
| Asset | Owner | Notes |
|---|---|---|
| Public GitHub repo with MIT or Apache-2.0 licence visible in About, `.kiro/` committed | agent + human | run `AUDIT` |
| Live app URL (GitHub Pages) | agent + human | must work with no keys and stay up until Jan 29 2027 |
| Demo video, under 3:00, public on YouTube | human | script below; no copyrighted music, no logos |
| Text description | agent drafts, human edits | features and functionality |
| Kiro write-up | agent drafts from `docs/kiro-journal.md`, human edits and signs off | only true statements |
| Blog post (bonus) | human writes, agent may proofread | public, third-party platform, published before the deadline |
| Social post (bonus) | human writes in own words | must START with `#KiroweenHackathon26` |
| Student details (bonus) | human only | LinkedIn, student email, year and degree, college name; they may ask for proof of enrollment |

## Demo video script (target 2:45)
| Time | Show | Say (in your own words) |
|---|---|---|
| 0:00 to 0:20 | Title card, then the unenforced replay's spend meter passing the allowance | Agents hold real credentials; a limit in a prompt is not a control |
| 0:20 to 0:45 | A slide with the verified Telescript facts only | 1994, permits, places, destroy-on-exceed, signed authority |
| 0:45 to 1:40 | Compare view: Run A then Run B | Same injected document. Without the runtime it exports records and overspends. With it: border imposes a narrower permit, export denied, allowance drains, KILLED, click the event to show why |
| 1:40 to 2:15 | Architecture diagram from the README | Agent only proposes; engine executes, meters, checks borders, kills |
| 2:15 to 2:40 | `.kiro/` tree, one spec, one property test, a hook run, the journal | How Kiro was used, with one real bug or surprise it surfaced |
| 2:40 to 2:55 | The "not stopped" note | Honest limits: injection inside the permit is not stopped; recorded runs are scripted |
Record on the laptop you built it on. Do a dry run with a timer. Upload to YouTube as public. Keep a copy.

## Kiro write-up template (delete any section that is not true)
- Surfaces used (IDE; CLI or others only if actually used) and why.
- Specs vs vibe coding: how each of the five specs was seeded, what review at the approval gates changed, what you did by chat instead and why.
- Steering: which files mattered most (likely `security-invariants.md` and `workflow.md`) and one concrete effect.
- Hooks: which ones you ran and what they caught.
- Property-based testing: the properties, plus at least one real counterexample or bug it found (from the journal).
- MCP, powers, custom agents: only if used; otherwise omit.
- Disclosure: "Planning documents (steering files and spec briefs) were drafted with an external AI assistant before building. All specs, code and tests in this repository were produced and run in Kiro. Standard libraries and the Vite/React toolchain are used as dependencies."

## Blog post outline (must say it was written as part of the Kiroween 2026 hackathon)
Title; one-paragraph hook; what Telescript's permits were (verified facts only); why runtime limits beat prompt limits; how TelePermit works; what Kiro made easy and hard (specs, property tests, hooks); honest limits; links to repo and demo.

## Social post
Write it yourself, start with `#KiroweenHackathon26`, share your favourite thing about Kiro and how it changed how you build. The organisers score originality and genuine insight, so do not paste AI-written text.

## AUDIT (command `AUDIT`; the agent prints PASS/FAIL per row)
| # | Check | How |
|---|---|---|
| 1 | Repo has remote and is the one submitted | `git remote -v` |
| 2 | Licence file present (MIT or Apache-2.0) | `head -3 LICENSE` |
| 3 | `.kiro` is tracked and not ignored | `git check-ignore -v .kiro` prints nothing; `git ls-files .kiro` lists steering, specs, hooks |
| 4 | Five spec folders each with requirements.md, design.md, tasks.md | `ls .kiro/specs/*` |
| 5 | Hooks committed | `ls .kiro/hooks` |
| 6 | No secrets committed | `git grep -nE "sk-ant-|ANTHROPIC_API_KEY=.+" -- . ':!.env.example'` returns nothing |
| 7 | Tests green | command `TEST` |
| 8 | Replays present and valid | `ls frontend/public/replays`; `test_replays.py` passes |
| 9 | README has all sections from Phase 6 and a live URL | read README |
| 10 | Telescript claims match telescript-facts.md | grep "Telescript" in README, docs, UI; compare |
| 11 | No logos or trademarks in UI, video assets | manual |
| 12 | Journal has real entries and at least one PBT finding (if none happened, say so in the write-up) | read journal |
| 13 | Human-only items: video public and under 3:00, live URL opens in a private window, blog and social live and before the deadline, Devpost form complete, student details ready | human confirms |
