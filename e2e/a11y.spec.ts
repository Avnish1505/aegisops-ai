import { actAs, axe, expect, test } from './fixtures'

const SCREENS: [string, string | RegExp][] = [
  ['/', /Incidents/],
  ['/plans/1', /Plan 1/],
  ['/triage', /Reports/],
  ['/audit/1', /Audit trail/],
  ['/evals', 'Evaluations'],
]

for (const theme of ['dark', 'light'] as const) {
  for (const [path, ready] of SCREENS) {
    test(`axe: ${path} (${theme})`, async ({ page }) => {
      await actAs(page, 'olive', theme)
      await page.goto(path)
      await expect(page.getByText(ready).first()).toBeVisible()
      await page.waitForLoadState('networkidle').catch(() => undefined)
      const results = await axe(page)
      const summary = results.violations.map((v) => `${v.id}: ${v.nodes.length} node(s) ${v.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`)
      expect(summary).toEqual([])
    })
  }
}

test('axe: sign-in screen', async ({ page }) => {
  await actAs(page, 'olive')
  await page.goto('/evals')
  await page.getByLabel('Acting as').selectOption('')
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  expect((await axe(page)).violations.map((v) => v.id)).toEqual([])
})
