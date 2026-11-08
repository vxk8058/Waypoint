// Placeholder AI response for the simulation page until the backend is wired up.
// Shape matches what AiDocument expects: { blocks: [...] }.

export const simulationSuggestions = [
  "Can I afford the car by Christmas?",
  "What if I cut dining out in half?",
  "What happens if I take a car loan instead?",
];

export function sampleSimulation(prompt: string) {
  return {
    blocks: [
      { type: "heading", props: { text: "Buying a car by Christmas", level: 1 } },
      { type: "paragraph", props: { size: "small", tone: "muted", text: `You asked: *${prompt}*` } },
      {
        type: "paragraph",
        props: {
          size: "lead",
          text: "You're on track to have **$6,000** saved by **December 20**, but only if you keep putting away about **$215 a week**.",
        },
      },
      {
        type: "stats",
        props: {
          items: [
            { label: "Saved so far", value: 2400, format: { style: "currency" }, caption: "40% of goal" },
            { label: "Needed per week", value: 215, format: { style: "currency" }, change: 18, goodDirection: "down", caption: "vs. current pace" },
            { label: "Chance on time", value: 72, format: { style: "percent" }, caption: "at current spending" },
          ],
        },
      },
      {
        type: "line_chart",
        props: {
          title: "Projected savings",
          subtitle: "Shaded area shows the likely range",
          x: ["Aug", "Sep", "Oct", "Nov", "Dec"],
          valueFormat: { style: "currency" },
          series: [
            {
              name: "Savings",
              values: [600, 1300, 2400, 4100, 6000],
              band: {
                lower: [null, null, 2400, 3700, 5100],
                upper: [null, null, 2400, 4400, 6600],
              },
            },
          ],
        },
      },
      { type: "heading", props: { text: "Where the extra money can come from", level: 2 } },
      {
        type: "paragraph",
        props: {
          text: "Dining is your most flexible category. Cutting it from **$512** to **$300** a month closes most of the gap without touching anything essential.",
        },
      },
      {
        type: "bar_chart",
        props: {
          title: "Monthly savings by change",
          orientation: "horizontal",
          sort: "desc",
          valueFormat: { style: "currency" },
          valueLabels: "all",
          highlight: ["Dine out less"],
          data: [
            { label: "Dine out less", value: 212 },
            { label: "Pause subscriptions", value: 45 },
            { label: "Pack lunch 3×/week", value: 96 },
            { label: "Skip one rideshare a week", value: 72 },
          ],
        },
      },
      {
        type: "callout",
        props: {
          tone: "info",
          title: "A loan would get you there sooner",
          text: "A $4,000 auto loan at 6.9% over 36 months adds about **$123/month**, and you could buy the car in early December.",
        },
      },
      {
        type: "gantt_chart",
        props: {
          title: "Your plan",
          today: new Date().toISOString().slice(0, 10),
          markers: [{ date: "2026-12-20", label: "Buy" }],
          tasks: [
            { id: "save", name: "Save $215/week", start: "2026-08-01", end: "2026-12-15", progress: 40, group: "Save" },
            { id: "dining", name: "Dining cap: $300/mo", start: "2026-11-08", end: "2026-12-20", group: "Save" },
            { id: "research", name: "Research models", start: "2026-11-08", end: "2026-11-30", group: "Buy" },
            { id: "test", name: "Test drives", start: "2026-12-01", end: "2026-12-14", group: "Buy", dependsOn: ["research"] },
            { name: "Buy the car", start: "2026-12-20", milestone: true, group: "Buy", dependsOn: ["save", "test"] },
          ],
        },
      },
      {
        type: "list",
        props: {
          items: [
            "Set up an automatic **$215** weekly transfer to Savings",
            "Cap dining at **$300** for November and December",
            "Revisit this plan on **Dec 1**",
          ],
        },
      },
      { type: "paragraph", props: { size: "small", tone: "muted", text: "Simulated with sample data. Not financial advice." } },
    ],
  };
}
