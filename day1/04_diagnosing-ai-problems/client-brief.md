# Client Brief — Meridian Support Pilot

*Prepared for Priya Anand, VP Customer Operations. Draft, 2026-11-12.*

---

**Client & pilot**
Meridian — an AI agent that triages and resolves customer support tickets (a coordinator routing to billing / technical / account specialists). Live 3 weeks; closing tickets that aren't actually resolved.

**Short answer**
It's fixable, and it isn't the model. The agent was doing exactly what its instructions told it to do, and two of those instructions were wrong. We changed them without touching the model. Resolution on the problem ticket went from 0% to roughly 75%, and on new tickets it hadn't seen, from untested to 100%.

**What's actually breaking it**
Two rules in the coordinator's instructions — the part that reads each ticket and decides who handles it:

1. **"One ticket, one specialist."** The coordinator was told that every ticket goes to exactly one specialist, even when the customer raises more than one problem. T-4471 had two: Okta SSO was down (an account issue) and a $1,200 overcharge (a billing issue). It sent the ticket to the account specialist every time. That specialist correctly found the SSO fault, and even confirmed the refund was owed, but it has no ability to issue refunds. Billing never saw the ticket.
2. **"Always mark it resolved; escalating is a last resort."** Once the specialist reported back, the coordinator was told to close the ticket as resolved, and that escalations count against the team's SLA. So when half the ticket was untouched, it closed it anyway and wrote replies like *"I've handed this over to our billing team… no further action needed."* No hand-off ever happened. That's the "resolved when it wasn't" your customer hit.

The model was capable throughout. In every run it diagnosed the SSO fault correctly (an expired signing certificate) and found the evidence for the refund. It was following orders.

**The fix**
One file: the coordinator's instructions (`system-prompt-coordinator.txt`).
- **Routing:** list every issue the customer raised and send each one to the specialist who owns it, at most one specialist per category. This replaces the "exactly ONE specialist" rule in step 5 and the classification guide.
- **Closing:** mark a ticket resolved only when every issue was actually acted on (a refund issued, a setting changed). Anything the agents can't do, such as an approval only staff can give, goes to a human, and the reply tells the customer plainly what's done and what's pending. This replaces step 6.

We also tried improving only the tool descriptions, leaving the instructions as they were. It didn't fix routing (3/9), because the explicit "one specialist" rule in the instructions overrode them. The fix has to live in the instructions.

**Proof** *(same model before and after: Claude Sonnet 5; each ticket run repeatedly, because single runs vary)*

| | Shipped | Fixed |
|---|---|---|
| T-4471 (SSO + refund) | **0 / 10** | **12 / 16** (~75%) |
| T-4490 — new ticket, technical + billing | not run | **11 / 11** |
| T-4503 — new ticket, 2FA reset + needs human sign-off | not run | **11 / 11** (escalated correctly every time) |
| Falsely marked "resolved" (T-4471) | 10 / 10 | at most 4 / 16 |
| Cost per ticket | $0.13 | $0.19 |

Cost rose about 50% because a ticket with two problems now gets two specialists, which is the point. The shipped system was cheap because it only did half the work.

**What it would take**
- **Ship the instruction change now.** It's a text change, it's measured, and it stops the false "resolved" in most cases.
- **One known gap before full rollout:** on T-4471 the billing specialist sometimes still doesn't issue the correct refund. It's brought in every time now; the miss is in its follow-through. Next step is tightening the billing specialist's instructions and refund tool, then re-measuring. Target: T-4471 at 5/5 across repeated runs, and cost held at or below ~$0.20 per ticket.
- **Keep the measurement in place.** The test set (T-4471 plus the two new tickets) should run on every prompt change before it ships. That's how you'll know a future edit hasn't broken it again.

**The objection we'll get: "Why not just pay for a better model?"**
We tested it.
- **On the system as shipped, model size made no difference.** The smallest, cheapest model (Haiku, $0.03 per ticket) and the one you're running (Sonnet, $0.13) both resolved **0 of 5**, failing in exactly the same way: one specialist, refund dropped, ticket closed as resolved. *(We didn't get Opus onto the unchanged system; that run was cut short.)*
- **Paying more only helps once the instructions are fixed.** On the fixed instructions, Opus resolved T-4471 5/5, at $0.36 per ticket, almost twice what fixed Sonnet costs. That's a possible later upgrade, not the fix: without the instruction change, a bigger model would have followed the same wrong rules.

The problem was never the model's intelligence. It was told to send every ticket to one place and to call it done.
