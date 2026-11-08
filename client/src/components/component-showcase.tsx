import { useState } from 'react'
import { Button } from './button'
import type { ButtonProps } from './button'
import { TextField } from './text-field'
import { Text } from './text'
import { AiComponent } from './ai-component'

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
]

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
          <h2 className="text-lg font-semibold">Bar chart (AI-driven)</h2>
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
