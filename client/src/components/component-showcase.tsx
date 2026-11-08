import { useState } from 'react'
import { Button } from './button'
import type { ButtonProps } from './button'
import { TextField } from './text-field'
import { Text } from './text'
import { AiComponent } from './ai-component'
import { AiDocument } from './ai-document'

// Example payloads exactly as the AI backend would send them.
const chartExamples = [
  {
    type: 'bar_chart',
    props: {
      title: 'Spending by category, October',
      subtitle: 'Dining is over its $400 budget',
      orientation: 'horizontal',
      sort: 'desc',
      valueFormat: { style: 'currency' },
      valueLabels: 'all',
      highlight: ['Dining'],
      referenceLines: [{ value: 400, label: 'Budget' }],
      data: [
        { label: 'Rent', value: 1450 },
        { label: 'Groceries', value: 386.4 },
        { label: 'Dining', value: 512.75 },
        { label: 'Transport', value: 142 },
        { label: 'Subscriptions', value: 64.97 },
      ],
    },
  },
  {
    type: 'bar_chart',
    props: {
      title: 'Income vs spending',
      subtitle: 'Last 6 months',
      categories: ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'],
      series: [
        { name: 'Income', values: [4200, 4200, 4650, 4200, 4200, 5100] },
        { name: 'Spending', values: ['3,890', 4410, 3720, 3950, null, 3610] },
      ],
      valueFormat: { style: 'currency' },
      valueAxis: { label: 'USD' },
    },
  },
  {
    type: 'bar_chart',
    props: {
      title: 'Where each paycheck goes',
      categories: ['Q1', 'Q2', 'Q3', 'Q4'],
      layout: 'stacked',
      valueFormat: { style: 'currency', compact: true },
      series: [
        { name: 'Needs', values: [6100, 6250, 6300, 6400] },
        { name: 'Wants', values: [2900, 3400, 2600, 3100] },
        { name: 'Savings', values: [2500, 2100, 3300, 3800], color: 'teal' },
      ],
      referenceLines: [{ value: 12000, label: 'Target' }],
    },
  },
  {
    type: 'bar_chart',
    props: {
      title: 'Monthly net cash flow',
      categories: ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'],
      series: [{ name: 'Net', values: [310, -210, 930, 250, -480, 1490] }],
      valueFormat: { style: 'currency' },
      valueLabels: 'min-max',
      height: 260,
    },
  },
  {
    type: 'line_chart',
    props: {
      title: 'Projected savings',
      subtitle: 'Shaded band is the 10th–90th percentile of 1,000 simulations',
      x: ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10', '2026-11', '2026-12'],
      forecastFrom: '2026-08',
      valueFormat: { style: 'currency' },
      referenceLines: [{ value: 12000, label: 'Car fund goal' }],
      series: [
        {
          name: 'Savings',
          values: [4200, 4900, 5300, 6100, 6650, 7400, 8100, 8900, 9700, 10500, 11300, 12100],
          band: {
            lower: [null, null, null, null, null, null, null, 8900, 9300, 9800, 10300, 10800],
            upper: [null, null, null, null, null, null, null, 8900, 10100, 11200, 12300, 13400],
          },
        },
      ],
    },
  },
  {
    type: 'line_chart',
    props: {
      title: 'Spending by category',
      x: ['Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov'],
      valueFormat: { style: 'currency' },
      series: [
        { name: 'Groceries', values: [420, 455, 390, 410, 386, 430] },
        { name: 'Dining', values: [260, 310, 380, 290, 512, 340] },
        { name: 'Transport', values: [150, 140, 160, 120, 142, 135] },
      ],
      highlight: ['Dining'],
    },
  },
  {
    type: 'histogram',
    props: {
      title: 'Transaction sizes, last 90 days',
      valueFormat: { style: 'currency' },
      countLabel: 'Transactions',
      markers: ['median', 'mean'],
      values: [4.5, 6.2, 8, 9.99, 11.5, 12, 12.75, 14, 15.3, 16, 18.4, 19.99, 21, 22.5, 23, 24.1, 25, 26.8, 28, 29.5, 31, 33, 34.2, 36, 38.5, 41, 44, 47.25, 52, 55, 58.9, 63, 68, 74.5, 82, 89, 96, 112, 128, 145, 162, 189, 240, 12.5, 18, 21.5, 24, 27, 9.5, 14.5, 16.8, 19, 22, 31.5, 35, 42, 48, 13, 17, 20, 23.5],
    },
  },
  {
    type: 'pie_chart',
    props: {
      title: 'Where October went',
      valueFormat: { style: 'currency' },
      data: [
        { label: 'Rent', value: 1450 },
        { label: 'Groceries', value: 386.4 },
        { label: 'Dining', value: 512.75 },
        { label: 'Transport', value: 142 },
        { label: 'Subscriptions', value: 64.97 },
        { label: 'Gifts', value: 90 },
      ],
    },
  },
  {
    type: 'scatter_plot',
    props: {
      title: 'Income vs savings rate',
      subtitle: 'Each dot is a month',
      xAxis: { label: 'Monthly income', format: { style: 'currency' } },
      yAxis: { label: 'Savings rate', format: { style: 'percent' } },
      trendline: 'all',
      highlight: ['Oct 2026'],
      points: [
        { x: 4200, y: 8, label: 'Jan 2026' },
        { x: 4200, y: 11, label: 'Feb 2026' },
        { x: 4350, y: 9, label: 'Mar 2026' },
        { x: 4200, y: 14, label: 'Apr 2026' },
        { x: 4650, y: 16, label: 'May 2026' },
        { x: 4200, y: 6, label: 'Jun 2026' },
        { x: 4650, y: 20, label: 'Jul 2026' },
        { x: 4200, y: 12, label: 'Aug 2026' },
        { x: 4800, y: 18, label: 'Sep 2026' },
        { x: 5100, y: 29, label: 'Oct 2026' },
      ],
    },
  },
  {
    type: 'gantt_chart',
    props: {
      title: 'Christmas car plan',
      today: '2026-11-07',
      markers: [{ date: '2026-12-20', label: 'Purchase' }],
      tasks: [
        { id: 'budget', name: 'Set budget', start: '2026-08-01', end: '2026-08-14', progress: 100, group: 'Plan' },
        { id: 'save', name: 'Save down payment', start: '2026-08-15', end: '2026-12-10', progress: 72, group: 'Save', dependsOn: ['budget'] },
        { id: 'research', name: 'Research models', start: '2026-09-01', end: '2026-10-31', progress: 100, group: 'Plan' },
        { id: 'loan', name: 'Get loan pre-approval', start: '2026-11-01', durationDays: 21, progress: 30, group: 'Plan', dependsOn: ['research'] },
        { id: 'test', name: 'Test drives', start: '2026-11-15', end: '2026-12-05', group: 'Buy', dependsOn: ['research'] },
        { name: 'Buy the car', start: '2026-12-20', milestone: true, group: 'Buy', dependsOn: ['save', 'loan', 'test'] },
      ],
    },
  },
]

// A full AI response: text and charts mixed, in the order the model sends them.
const documentExample = {
  blocks: [
    { type: 'heading', props: { text: 'Your October in review', level: 1 } },
    {
      type: 'paragraph',
      props: {
        size: 'lead',
        text: 'You spent **$2,646** this month, about 6% less than September, and you put **$610** into savings.',
      },
    },
    {
      type: 'stats',
      props: {
        items: [
          { label: 'Spent', value: 2646.12, format: { style: 'currency' }, change: -6.2, goodDirection: 'down', caption: 'vs. September' },
          { label: 'Saved', value: 610, format: { style: 'currency' }, change: 14, caption: 'vs. September' },
          { label: 'Savings rate', value: 13, format: { style: 'percent' }, change: '+2 pts', caption: 'vs. September' },
        ],
      },
    },
    {
      type: 'bar_chart',
      props: {
        title: 'Spending by category',
        subtitle: 'October',
        valueFormat: { style: 'currency' },
        orientation: 'horizontal',
        sort: 'descending',
        highlight: ['Dining'],
        data: [
          { label: 'Rent', value: 1450 },
          { label: 'Dining', value: 512.75 },
          { label: 'Groceries', value: 386.4 },
          { label: 'Transport', value: 142 },
          { label: 'Gifts', value: 90 },
          { label: 'Subscriptions', value: 64.97 },
        ],
      },
    },
    { type: 'heading', props: { text: 'Dining is the one to watch', level: 2 } },
    {
      type: 'paragraph',
      props: {
        text: 'Dining came in **$112 over budget**, mostly from weekend takeout. Everything else stayed under.\n\nRent is still more than half of your spending, so the split below barely moves month to month.',
      },
    },
    {
      type: 'callout',
      props: { tone: 'warning', title: 'Dining is 28% over budget', text: 'Cutting two takeout orders a week would bring it back to *$400*.' },
    },
    {
      type: 'pie_chart',
      props: {
        title: 'Where October went',
        valueFormat: { style: 'currency' },
        data: [
          { label: 'Rent', value: 1450 },
          { label: 'Groceries', value: 386.4 },
          { label: 'Dining', value: 512.75 },
          { label: 'Transport', value: 142 },
          { label: 'Subscriptions', value: 64.97 },
          { label: 'Gifts', value: 90 },
        ],
      },
    },
    { type: 'heading', props: { text: 'Side by side', level: 2 } },
    {
      type: 'row',
      props: {
        blocks: [chartExamples[4], chartExamples[6]],
      },
    },
    { type: 'list', props: { items: ['Set a **$400** dining cap for November', 'Move the $90 gift budget into December', 'Review subscriptions: $64.97/mo'] } },
    { type: 'paragraph', props: { size: 'small', tone: 'muted', text: 'Based on transactions synced through Oct 31.' } },
  ],
}

const variants: NonNullable<ButtonProps['variant']>[] = [
  'primary',
  'secondary',
  'outline',
  'ghost',
  'danger',
]
const sizes: NonNullable<ButtonProps['size']>[] = ['sm', 'md', 'lg']

export function ComponentShowcase() {
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const usernameError =
    username.length > 0 && username.length < 3 ? 'Must be at least 3 characters' : undefined

  return (
    <main className="min-h-screen px-4 py-12">
      <div className="mx-auto max-w-4xl space-y-10">
        <header>
          <h1 className="text-4xl font-bold tracking-tight">Waypoint</h1>
          <p className="mt-2 text-blue-grey-400">Button preview</p>
        </header>

        <section className="space-y-8 rounded-xl border border-blue-grey-800 bg-surface p-6">
          <h2 className="text-lg font-semibold">Typography</h2>

          <div className="space-y-4">
            <Text variant="overline">Overline</Text>
            <Text variant="display">Display</Text>
            <Text variant="h1">Heading 1</Text>
            <Text variant="h2">Heading 2</Text>
            <Text variant="h3">Heading 3</Text>
            <Text variant="h4">Heading 4</Text>
            <Text variant="lead">
              Lead — a larger intro paragraph that sits under a page heading.
            </Text>
            <Text>
              Body — the default for paragraphs. Waypoint helps you plan the route between where
              you are and where you want to be.
            </Text>
            <Text variant="small">Small — secondary details and compact UI copy.</Text>
            <Text variant="caption">Caption — timestamps, footnotes, metadata.</Text>
            <Text variant="label">Label — form labels and small UI headings</Text>
          </div>

          <div className="space-y-2">
            <Text variant="h4">Tones</Text>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <Text>default</Text>
              <Text tone="muted">muted</Text>
              <Text tone="subtle">subtle</Text>
              <Text tone="primary">primary</Text>
              <Text tone="accent">accent</Text>
              <Text tone="danger">danger</Text>
              <Text tone="warning">warning</Text>
              <Text tone="inverse" className="rounded bg-blue-grey-050 px-2">
                inverse
              </Text>
            </div>
          </div>

          <div className="space-y-2">
            <Text variant="h4">In context</Text>
            <div className="max-w-md space-y-2 rounded-lg border border-blue-grey-700 p-5">
              <Text variant="overline" tone="accent">
                Next stop
              </Text>
              <Text variant="h3" as="h3">
                Austin, TX
              </Text>
              <Text tone="muted">
                3h 12m drive · 195 miles. Leave by 2:30 PM to arrive before sunset.
              </Text>
              <Text variant="caption">Updated 5 minutes ago</Text>
            </div>
          </div>
        </section>

        <section className="space-y-4 rounded-xl border border-blue-grey-800 bg-surface p-6">
          <h2 className="text-lg font-semibold">Variants × sizes</h2>
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-y-3">
              <thead>
                <tr className="text-left text-sm text-blue-grey-400">
                  <th className="pr-6 font-medium">Variant</th>
                  {sizes.map((size) => (
                    <th key={size} className="pr-6 font-medium">
                      {size}
                    </th>
                  ))}
                  <th className="font-medium">disabled</th>
                </tr>
              </thead>
              <tbody>
                {variants.map((variant) => (
                  <tr key={variant}>
                    <td className="pr-6 text-sm font-medium text-blue-grey-300">{variant}</td>
                    {sizes.map((size) => (
                      <td key={size} className="pr-6">
                        <Button variant={variant} size={size}>
                          Button
                        </Button>
                      </td>
                    ))}
                    <td>
                      <Button variant={variant} disabled>
                        Button
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-4 rounded-xl border border-blue-grey-800 bg-surface p-6">
          <h2 className="text-lg font-semibold">Full width</h2>
          <div className="max-w-sm space-y-3">
            <Button fullWidth>Sign in</Button>
            <Button fullWidth variant="outline">
              Create account
            </Button>
          </div>
        </section>

        <section className="space-y-6 rounded-xl border border-blue-grey-800 bg-surface p-6">
          <h2 className="text-lg font-semibold">Text fields</h2>

          <div className="grid gap-6 sm:grid-cols-2">
            <TextField label="Default" placeholder="Type something…" fullWidth />
            <TextField
              label="With hint"
              placeholder="you@example.com"
              type="email"
              hint="We'll never share your email."
              required
              fullWidth
            />
            <TextField
              label="Error"
              defaultValue="abc"
              error="Password is too short"
              fullWidth
            />
            <TextField label="Disabled" value="Can't edit this" disabled readOnly fullWidth />
            <TextField
              label="Leading icon"
              placeholder="Search destinations"
              leading={<span aria-hidden>🔍</span>}
              fullWidth
            />
            <TextField
              label="Trailing action"
              type={showPassword ? 'text' : 'password'}
              defaultValue="hunter2"
              trailing={
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="cursor-pointer text-sm font-medium text-purple-300 hover:text-purple-200"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              }
              fullWidth
            />
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-medium text-blue-grey-400">Sizes (aligned with buttons)</h3>
            {sizes.map((size) => (
              <div key={size} className="flex items-end gap-3">
                <TextField size={size} placeholder={`Size ${size}`} aria-label={`Size ${size}`} />
                <Button size={size}>Go</Button>
              </div>
            ))}
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-medium text-blue-grey-400">Live validation</h3>
            <TextField
              label="Username"
              placeholder="Try typing 1–2 characters"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              error={usernameError}
              hint="3–20 characters"
            />
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-lg font-semibold">AI response (text + charts)</h2>
          <div className="rounded-xl border border-blue-grey-800 bg-canvas p-6">
            <AiDocument document={documentExample} />
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Charts (AI-driven)</h2>
          <div className="grid gap-6 lg:grid-cols-2">
            {chartExamples.map((block, i) => (
              <AiComponent key={i} block={block} />
            ))}
          </div>
        </section>

        <section className="space-y-4 rounded-xl border border-blue-grey-800 bg-surface p-6">
          <h2 className="text-lg font-semibold">In context</h2>
          <div className="flex flex-wrap justify-end gap-3">
            <Button variant="ghost">Cancel</Button>
            <Button variant="danger">Delete</Button>
            <Button>Save changes</Button>
          </div>
        </section>
      </div>
    </main>
  )
}

export default ComponentShowcase
