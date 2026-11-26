# Your guest assistant: delivery guide

This guide is for you, the host. It explains what you own, what it costs, what you can do yourself, and what to ask me.

Your guests open a link (or scan a QR code) and ask questions about their stay in their own language. The assistant answers only from your house guide, says which document the answer came from, and says so when the guide does not have the answer.

Prices and terms below were checked on Google's and PythonAnywhere's websites on 24–25 November 2026. They can change; the links are included so you can check them.

---

## 1. Your accounts: you own them and you pay for them

The assistant runs on two services. Both accounts are in **your name, with your card**. I set things up, but I am never the owner, so the API key, the bills and the data stay yours.

| Service | What it does | Cost |
|---|---|---|
| **Google AI Studio / Google Cloud** | The AI model (Gemini) that writes the answers | Pay per use, a few US dollars a month (see section 3) |
| **PythonAnywhere**, *Developer* plan | Hosts the web page your guests open | US$10 per month ([pricing](https://www.pythonanywhere.com/pricing/)) |

**PythonAnywhere in the EU.** PythonAnywhere has a separate EU site, **eu.pythonanywhere.com**, which it announced with its servers in Frankfurt ([announcement](https://blog.pythonanywhere.com/176/)). Its privacy policy (version 2.0, effective 10 May 2018, written before the EU site opened) says that personal information collected on the EU-hosted service is stored within the EU and not transferred to other countries ([privacy policy](https://eu.pythonanywhere.com/privacy_v2/), section 11.1). This policy is old, so please check PythonAnywhere's current privacy policy when you create the account. Please create your account on **eu.pythonanywhere.com**. Your guest link will then look like `https://yourname.eu.pythonanywhere.com/p/...`.

### What you do yourself (about 15 minutes)

1. Create a Google account for the business, if you don't have one.
2. Create a project in Google Cloud ([how](https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects)).
3. Turn on billing with your card. I recommend **prepaid billing** (see section 2).
4. Give me access to the project: **IAM → Grant access**, add my email, and choose only these roles ([how](https://docs.cloud.google.com/iam/docs/granting-changing-revoking-access)):
   - **Service Usage Admin**, so I can turn on the Gemini API;
   - **API Keys Admin**, so I can create the key the assistant uses.
   - Optional: **Billing Account Costs Manager** on your billing account, so I can create a budget alert for you.

   Please do **not** make me *Owner*. You can remove my access at any time on the same IAM page.
5. Create a PythonAnywhere **Developer** account on eu.pythonanywhere.com.

PythonAnywhere has no documented way to give another person limited access to an account. We do the PythonAnywhere part together in a short screen-share call: you stay logged in, and I never need your password.

---

## 2. Gemini: the paid plan is required with real guests

Google's Gemini API has a free tier, but it cannot be used for your guests:

- Google's terms say: *"You may use only Paid Services when making API Clients available to users in the European Economic Area, Switzerland, or the United Kingdom."* ([Gemini API terms](https://aistudio.google.com/docs/terms), effective 23 March 2026)
- On the free tier ("Unpaid Services"), Google uses the content you submit and the answers *"to provide, improve, and develop"* its products, and *"human reviewers may read, annotate, and process your API input and output."*
- On the paid tier ("Paid Services"), Google *"doesn't use your prompts"* (or the files and instructions sent with them) *"or responses to improve our products"*, and *"logs prompts and responses for a limited period of time, solely for detecting and preventing violations"* of its Prohibited Use Policy (and for any required legal or regulatory disclosures).

### A spending limit: prepaid billing

In Google AI Studio, **Set up billing** lets you pay in advance. New accounts start on prepaid billing, and the minimum purchase of credits is US$5. When the prepaid balance reaches $0, the API keys linked to that billing account stop working until you add credits, so you can never spend more than you put in ([billing](https://aistudio.google.com/docs/billing)). The assistant then stops answering until you top up.

A **budget alert** in Google Cloud only sends you emails: *"Setting an alerts-only budget doesn't automatically cap Google Cloud or Google Maps Platform usage or spending."* ([budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets)). Prepaid billing is the real limit.

### Turning off Google's request logs

Google AI Studio can keep a copy of every question and answer in your project's **logs**. For the kind of request the assistant makes, this is **on by default** in projects created on or after 26 October 2026, and logs are kept for a default maximum of 55 days ([logs policy](https://aistudio.google.com/docs/logs-policy)). That would contradict what the privacy notice tells your guests (conversations deleted after 24 hours).

The logs policy says: *"As a project owner, you can turn logging on or off at any time from the Logs page in AI Studio."* You are the project owner, so you do it, together with me during the setup call. Please never share these logs as a dataset with Google.

---

## 3. What it costs

Measured on 25 November 2026 with the real API and the example house guide (7 short documents): each question sends about **2,800 tokens** (the whole guide plus the question) and gets back **160 to 970 tokens** (the answer plus the model's "thinking", which is billed as output; about 530 on average).

Prices per million tokens, standard paid tier ([Gemini API pricing](https://aistudio.google.com/docs/pricing), checked 24–25 November 2026):

| Model | Used for | Input | Output |
|---|---|---|---|
| gemini-3.5-flash-lite | every question | $0.30 | $2.50 |
| gemini-3.6-flash | only when the main model is busy | $0.75 until 31 Dec 2026, then $1.50 | $3.75 until 31 Dec 2026, then $7.50 |

| | Per question | 30 questions a day (≈ 900 a month) |
|---|---|---|
| gemini-3.5-flash-lite (normal case) | about $0.002 (between $0.001 and $0.003) | **about $2 a month** (between $1.10 and $2.95) |
| gemini-3.6-flash, until 31 Dec 2026 | about $0.004 | about $3.70 a month if *every* question used it |
| gemini-3.6-flash, from 1 Jan 2027 | about $0.008 | about $7.40 a month if *every* question used it |

The gemini-3.6-flash lines use the token counts measured with the first model; its own "thinking" may be longer. The second model only answers when the first one is busy, so a normal month costs close to the first line. A longer house guide costs more, in proportion to its length. Add PythonAnywhere: US$10 a month.

The assistant also has a **daily limit** of questions for all guests together (200 by default) and an **hourly limit per guest** (20 by default), so a mistake or an abuser cannot run up a large bill.

---

## 4. What you can do yourself

All of this is on your **host page**: `https://yourname.eu.pythonanywhere.com/host`.

- **Log in** with the host password. For safety, you are logged out after 8 hours or when you close the browser, and the page blocks logins after several wrong passwords.
- **Add or replace documents** in a property's guide: *Manage guide → Upload*. You can choose several files at once. Files can be `.md`, `.txt` or `.pdf`, up to 5 MB in total per upload. A file with the same name replaces the old one. Answers use the new guide straight away.
- **Delete a document**: *Delete* next to its name.
- **Print the QR code**: *Download QR code* on the property's page. It is a PNG ready to print, about 10 cm wide. Before printing, scan it with your phone and check that your guest page opens.
- **Change the host password**. In PythonAnywhere, open a **Bash console** and run:

  ```bash
  workon chatbot
  cd ~/Chatbot
  python set_host_password.py
  ```

  Type the new password twice (at least 10 characters). Copy the line it prints (`HOST_PASSWORD_HASH='...'`), open the `.env` file in the **Files** tab, replace the old `HOST_PASSWORD_HASH` line with it, save, and press **Reload** on the **Web** tab. The password itself is never saved anywhere, only a scrambled version of it. If you forget it, simply set a new one.

**Writing a good guide:** short, clear documents work best (check-in, the house, house rules, getting here, the neighbourhood, bookings, emergencies). **Do not put the door or key-box code in the guide**: anyone with the link can ask for it. Send it to each guest separately.

---

## 5. Important things to know

- **Never change a property's link after printing its QR code.** The link (the part after `/p/`) and the web address are printed inside the QR code. If either changes, every printed QR code and every link you have sent stops working.
- **Conversations are deleted after 24 hours.** Each guest's conversation is saved so they can see it on the page; it is deleted 24 hours after their last message (when the page is next opened). Only the last 20 questions are kept.
- **Privacy notice and age.** Under the question box, guests see a short line saying questions go to Google's Gemini AI and that they should not write personal data, with a link to the full notice. The notice names you (from your settings) and says the assistant is for guests aged 18 or over. Google's terms say: *"You must be 18 years of age or older to use the APIs."* They also do not allow using the API in a website or app *"that is directed towards or is likely to be accessed by individuals under the age of 18."*
- **Limits.** When a guest reaches the hourly limit, or all guests together reach the daily limit, they see a friendly message in their language. The daily limit restarts at midnight (UTC).
- **"The assistant is busy right now".** Google's service is sometimes overloaded. The assistant tries again, then tries the second model, and gives up after 40 seconds so the guest never waits longer.
- **The assistant can still be wrong.** It only uses your guide and says when something is not there, but like any AI it can make mistakes. Keep important information clear and up to date.

---

## 6. Your settings: what you can change, and what to ask me

The settings of each property are in the file `dados/config.toml` (in the **Files** tab). After any change, press **Reload** on the **Web** tab.

| You can change it yourself | Ask me |
|---|---|
| `name`: the property's name | Adding or removing a property |
| `color`: the main color, like `#1f4e8c` | **`slug`** (the link): never change it yourself, see section 5 |
| `logo`: a PNG or JPG up to 500 KB, in the property's folder | The web address (domain) |
| `not_found_message`: what guests are told when the guide has no answer, e.g. *"Please message the host on Airbnb."* | The limits, the AI model and anything in the `.env` file except the host password |
| `host_contact`: shown to guests and in the privacy notice | Updates to the assistant itself |

If the file has a mistake, the assistant does not start and the error log on the **Web** tab says what is wrong. Undo your change, press **Reload**, and ask me if needed.

---

## 7. Your guests' data (GDPR)

You decide that your guests use this assistant, so **you are responsible for your guests' personal data** under the GDPR. This section is not legal advice; it only describes, as facts, how the assistant handles data, to help you with your own privacy information.

| Data | Where it is | How long |
|---|---|---|
| A guest's questions and answers | Your PythonAnywhere account, linked to a random code in a browser cookie, **not** to a name | Deleted 24 hours after the guest's last message (when the page is next opened); only the last 20 questions are kept |
| The question and your house guide, sent to get each answer | Google's Gemini API (paid tier) | Not used to improve Google's products; kept by Google *"for a limited period of time"* to detect abuse; AI Studio logs turned off at setup |
| The random guest code; the IP address of failed host logins | A small counters file in your PythonAnywhere account, for the limits | Each counter expires with its time window (15 minutes to 1 day) and is then deleted |
| Visits to the site (IP address, page, browser) | PythonAnywhere's own server logs | As set by PythonAnywhere's [privacy policy](https://eu.pythonanywhere.com/privacy_v2/) |
| The documents you upload | Your PythonAnywhere account | Until you delete them |

Also:

- The assistant's own log records only counts and errors (for example "a guest reached the hourly limit"), **never the text of a question**.
- There are no analytics, ads or tracking cookies. The only cookie keeps the guest's conversation and, for you, the host login.
- Guests are asked not to write personal data (names, ID or passport numbers, card details, health information).

---

## 8. If something stops working

| What you see | What to do |
|---|---|
| "The assistant is busy right now" | Google's service is overloaded. Wait a minute and try again. If it lasts for hours, tell me. |
| The assistant stops answering for everyone | Check your prepaid balance in Google AI Studio and top up. |
| "The assistant is not set up yet" | The API key is missing or wrong. Tell me. |
| The page does not open at all | On PythonAnywhere's **Web** tab, press **Reload**. If it still fails, open the **error log** on the same tab and send me the last lines. |
| A guest cannot open the QR code | Scan it yourself: does it open your guest page? If not, tell me. |
| You forgot the host password | Set a new one (section 4). |
| The PythonAnywhere plan is not renewed (for example, the card expired) | The page goes offline for your guests. Renew the plan on PythonAnywhere's **Account** page, then press **Reload** on the **Web** tab. |

For anything else, contact me. I can usually look at it with you in a short screen-share call.

---

## 9. Support

Your package: **[PACKAGE]**

| Package | What is included |
|---|---|
| **Essential** | The assistant set up for 1 property, with your house guide |
| **Complete** | Up to 3 properties, each with its own guide and link, your logo and colors, and a printable QR code for each property |
| **Premium** | Everything in Complete, plus updates to your house guides for 3 months |

Support period: **[SUPPORT PERIOD]**. During this period, contact me if something in section 8 does not solve the problem, or if the assistant does not work as described in this guide.
