# jobless_doppelganger

*Your jobless double. It applies for you while you do something else.*

**Your job-application agent inside Claude. It learns your story and the way you write, finds the
remote jobs that fit you, and fills in the forms for you. You just say "send".**

[Español](README.md) · Free and open source (MIT)

---

Looking for a remote job is a second job. Ten job boards, listings that turn out to be "US only" in
the fine print, writing for the fifth time this week why you'd like to work somewhere, retyping your
experience into a form that won't read your CV. Forty minutes per application, and most never answer.

Your doppelganger does that work with you inside Claude:

| | What it does | What you skip |
|---|---|---|
| **1. Start** | Creates your private data folder, connects Claude to your Chrome, and gets you signed in to GetOnBoard and LinkedIn. | Setup. It takes 10 minutes. |
| **2. Profile** | Reads your CV, your LinkedIn and your past applications. Builds your profile (facts only, each with its source) and learns how you write. No CV? It asks for one or builds it with you. | Explaining who you are to every form. |
| **3. Improve your CV** | Compares your CV and LinkedIn with what real listings for your role ask for, and tells you what to change, why, and how it reads, ready to paste. | Guessing why nobody calls. |
| **4. Radar** | Sweeps GetOnBoard, Himalayas, Remotive, RemoteOK, Working Nomads and the job boards of a list of 340 companies that hire remotely (on a given day, about half have open listings). Filters by your role, salary floor and country. Ranks by fit. | Hours of scrolling and listings that were never for you. |
| **5. Apply** | Builds batches of 5–10 listings, writes every answer in your voice, shows you everything at once, and with your OK (or in auto mode) fills and submits the forms (GetOnBoard, Greenhouse, Ashby, Lever, Workable). | The forty minutes per application. |

## What makes it different

**It writes like you, not like ChatGPT.** It learns your tone from things you wrote. Before any
answer reaches a form, a checker screens it for AI phrasing ("I'm passionate about...", "leverage"),
em-dash habits, bullets where they don't belong, and padding. If it sounds like a bot, it gets rewritten.

**It writes only from your facts.** Before sending, a checker rejects an answer that carries a number,
a degree or a name (client, tool, company) that is in neither your profile nor the listing. What it
doesn't know, it asks, and saves for next time. The checker is a text filter and can miss things,
which is why every answer it sends is saved for you to read.

**It sells with proof, not adjectives.** For each listing it picks the evidence that matters to that
company: the number, the client, the project. "You need X; I did Y" beats "I'm a proactive, results-driven professional".

**It searches where you can actually apply.** Listings with a direct application form and no account
come first, and "remote" jobs that require living in the US get filtered out.

**You choose how much to look at.** By default you see every answer exactly as it will be sent and
give one yes per batch. If you'd rather not look, turn on auto mode (`"envio": "automatico"` in your
config): say "apply" and it sends only what clears every filter (high fit, direct form, no question
that only you can answer, up to 15 a day). Anything doubtful stays as a draft, and at the end it shows
you what it sent, answer by answer. In both modes, passwords, codes and CAPTCHAs are yours to enter,
and on LinkedIn you press the final button.

**Your data lives on your computer.** Everything about you is in `~/.doppelganger`. The plugin has no
server of its own and sends your data to no one. Claude reads it to do the work, like any file you
show it, and each form receives what you approve sending.

## Install

You need [Claude Code](https://claude.com/claude-code) and, to read LinkedIn and fill forms, the
**Claude in Chrome** extension (paid Claude plans). Python 3.9+ (preinstalled on Mac and Linux).

**From GitHub** (inside Claude Code):

```
/plugin marketplace add Sebyrz/jobless_doppelganger
/plugin install jobless-doppelganger@jobless-doppelganger
```

**From the zip:** unzip it anywhere and, inside Claude Code:

```
/plugin marketplace add /path/to/jobless_doppelganger
/plugin install jobless-doppelganger@jobless-doppelganger
```

Then type **"set up my doppelganger"** and follow along. The agent replies in your language;
the docs and script messages are in Spanish.

## What it won't do

- Invent experience, years, degrees or results.
- Send anything unless you ask in the chat: in normal mode, one yes per batch; in auto mode, your
  "apply" in that session. A scheduled run without you prepares the batch and sends nothing.
- Automate LinkedIn: it reads with you present and you press submit. LinkedIn bans bots, and your
  account is worth more than ten applications.
- Create accounts or type your passwords.
- Sign statements for you ("I didn't use AI", certifications): it shows them to you and you decide.
- Guarantee interviews. It gets you more good applications per hour, in your own voice.

## Under the hood

```
skills/        empezar · perfil · mejorar-cv · radar · postular (+ form-filling playbook)
scripts/       radar, sources, fit criteria, guardia (answer checker), queue and log
plantillas/    templates copied to ~/.doppelganger on first run
tests/         python3 -m unittest discover -s tests
```

Python standard library only. No dependencies, no servers, no API keys.

MIT license. Made to be given away.
