# P4 demo notes

## Slide outline

1. **JalLekha workflow** — ward evidence informs a draft allocation; an officer reviews it; drivers record delivery; resident reports and feedback inform later review.
2. **Hyderabad pilot evidence** — HMWSSB public tanker booking and delivery records provide a Hyderabad service baseline. Hyderabad is the pilot because these local records are available for the prototype.
3. **Review and accountability** — show the officer's evidence, plan, explanation, contest, and impact views. Make it clear where screens use simulated examples.
4. **Resident access** — show the report queue and sample ward card/SMS. Call out that sample OTPs and schedules are not live service data.

## Three-minute script

JalLekha is a decision-support prototype for sharing tanker water more fairly. It brings evidence about water access and service history into one place, then gives officers a draft plan they can review before taking action.

The workflow starts with ward evidence. The system combines the available need and service signals, then applies queue and allocation rules to produce a daily plan. Routing information can help turn that plan into a sequence of stops. Before approval, the officer can review confidence flags and the reasons behind a booking's place in the queue. After a delivery, proof and resident feedback can update the record used in a later plan. Residents can also report shortages or other water issues, including when they are offline; the app keeps those reports on the device until it can sync.

For the Hyderabad pilot, we use public HMWSSB tanker booking and delivery records. We selected Hyderabad because those local records were available for the prototype. They give us a real service baseline, while the planning and impact screens clearly label simulated results as examples rather than observed outcomes.

In the demo, I’ll show the officer's evidence and draft-plan screens, then open a booking explanation and sample contest. I’ll finish with the resident report and ward-card views. Those screens demonstrate the intended workflow, but sample OTPs, schedules, forecast ranges and contests do not connect to a live operations service. The next step is to connect the screens to the agreed APIs and replace each sample with verified service data.

## Demo run

From the repository root:

```powershell
npm ci --prefix frontend
npm run dev --prefix frontend
```

Open the Vite URL shown in the terminal. The main interface works without backend services; map tiles are the only external visual dependency. Choose **Officer** to visit Water access, Forecast & shortage, Allocation plan, Impact, and Explanations & contests. Choose **Resident** to open Report an issue, My requests, and Ward updates. Change the language picker to Telugu, Urdu, or Hindi to preview localization and Urdu right-to-left layout.

Screens labelled **SYNTHETIC** or **SIMULATION** are previews. No demo contest reply, approval, OTP or sample schedule updates a backend or ledger. Native-language review and live T10 routes remain follow-up work.

## Release tag

Create the release tag after this work merges to `main`, required checks pass, and the project owner confirms the version. This branch is not a release point.
