# Recording script: Proven demo, 2-minute cut

Video: `out/proven-demo-2min.mp4` (1:58). 15 lines, 244 words.

How to record:

- Record each line as its own take, named `line-01.wav` to `line-15.wav`.
- Each line has a slot. Start speaking at "start" and finish before "end by". The pace is calm, about two words a
  second; if a take runs long, say it again rather than rushing.
- Say numbers exactly as written. Words in **bold** take the stress.
- Play the video muted while you read: the subtitles show the same words at the right moment.

Suggested speakers (change freely): **A** opens and closes, **B** walks through the product, **C** does the safety
gate and the next close.

| # | Speaker | Start | End by | What is on screen |
|---|---|---|---|---|
| 01 | A | 0:00.5 | 0:07.5 | The sentence "Legal costs rose $90K because of our Series B" |
| 02 | B | 0:08.5 | 0:12.5 | Commentary pasted into the console, Verify pressed |
| 03 | B | 0:13.0 | 0:18.0 | Verdicts and the Coverage panel |
| 04 | B | 0:18.0 | 0:24.0 | Claim 1 fails: stated $90K, ledger +$44,900 |
| 05 | B | 0:24.5 | 0:31.5 | The $45,100 invoice booked to Marketing |
| 06 | B | 0:32.5 | 0:40.0 | Second company, Claude Sonnet as proposer |
| 07 | B | 0:40.5 | 0:48.5 | Claim marked REVIEW, matched on "campaign" |
| 08 | C | 0:49.5 | 0:57.5 | Safety gate result: safe |
| 09 | C | 0:58.0 | 1:05.5 | Reviewer ticks the box, records; claim turns PASS |
| 10 | C | 1:06.5 | 1:17.0 | Third company, Rules (offline), claim passes |
| 11 | A | 1:18.0 | 1:28.5 | Architecture diagram |
| 12 | A | 1:29.0 | 1:39.5 | 100% blocked, 100% never rejected, then 81.7% |
| 13 | A | 1:40.0 | 1:48.0 | Pre-registered test: 100% of 429 blocked |
| 14 | A | 1:49.0 | 1:53.5 | "Your machine" box |
| 15 | A | 1:54.5 | 1:57.0 | Proven wordmark |

## The lines

**01 · A · 7.0 s**
Every month-end close, finance teams explain **why** each number moved. Proven **checks** those explanations
against the ledger.

**02 · B · 4.0 s**
Paste the month's commentary and press **Verify**.

**03 · B · 5.0 s**
Each claim gets a **verdict**, and Coverage shows how much was checked.

**04 · B · 6.0 s**
Legal says **ninety** thousand; the ledger shows about **forty-five**.

**05 · B · 7.0 s**
The evidence shows why: a forty-five-thousand-dollar Series B invoice was booked to **Marketing**.

**06 · B · 7.5 s**
Here a language model proposes the claims. It sees the text and chart of accounts, **never** a transaction.

**07 · B · 8.0 s**
Its word, **campaign**, found the cause. But only the model's word supports it, so the claim **waits for a
person**.

**08 · C · 8.0 s**
The safety gate replays the lesson against explanations with known answers: **no** wrong one passes, and **no**
right one fails.

**09 · C · 7.5 s**
The reviewer checks the two transactions and confirms it **once**. The claim passes.

**10 · C · 10.5 s**
On the next close, at **another** company, the rules run alone. The same reason passes on the learned word. No
model ran; **nothing left the machine**.

**11 · A · 10.5 s**
The model only **proposes**; its reply has no verdict field. Deterministic code **decides** from the ledger, and
each confirmed lesson moves work from people to rules.

**12 · A · 10.5 s**
On every benchmark, **every** wrong explanation is blocked, and **no** correct one is rejected. On eleven unseen
companies, with Sonnet proposing, almost **eighty-two percent** are decided.

**13 · A · 8.0 s**
Then we **froze** the checker, wrote thirteen new companies, and scored **once**: **all** four hundred twenty-nine wrong
explanations were blocked.

**14 · A · 4.5 s**
Next: a **local** open-weight proposer, so no sentence leaves the building.

**15 · A · 2.5 s**
The model proposes. The **ledger** decides.

## If you change a line

The subtitles are driven by `src/timeline.ts` (`VO`) and mirrored in `docs/script.md`, which also lists the source
of every number. Change the words in all three places and keep each line inside its slot. Do not add a number that
is not on screen, and do not say the local model matches Sonnet: it does not yet.
