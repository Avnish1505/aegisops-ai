import { actAs, expect, test } from './fixtures'

test('triage -> plan -> review -> approve by a different user', async ({ page }) => {
  await actAs(page, 'olive')
  await page.goto('/triage')

  // An operator confirms an unread report by hand (no model in this environment).
  const queue = page.getByRole('listbox', { name: /Reports/ })
  await queue.getByRole('option', { name: /Kaiserbagh bus stand/ }).click()
  await expect(page.getByText('Not read by the model yet')).toBeVisible()
  await page.getByLabel('Incident type').selectOption('flood')
  await page.getByLabel(/Search places/).fill('qaisar')
  await page.getByRole('list', { name: 'Place results' }).getByRole('button').first().click()
  await page.getByLabel('People affected').fill('30')
  await page.getByRole('button', { name: 'Add need' }).click()
  await page.getByLabel('Resource type').selectOption('boat')
  await page.getByLabel('Quantity').fill('2')
  await page.getByLabel('trapped').check()
  await expect(page.getByText(/Severity by rule/)).toContainText('High')
  await page.getByRole('button', { name: 'Confirm and add to exercise' }).click()
  await expect(page.getByText(/Added to the exercise as/)).toBeVisible()

  await page.getByRole('button', { name: 'Plan the exercise now' }).click()
  await page.waitForURL(/\/plans\/\d+$/)
  const planId = page.url().split('/').pop()
  await expect(page.getByRole('heading', { level: 1 })).toContainText(`Plan ${planId}`)
  await expect(page.getByRole('table', { name: /Assignments/ })).toContainText(/INC-TRI-\d+/)

  // The operator who proposed it cannot approve (role), only reject.
  await expect(page.getByRole('button', { name: /Approve/ })).toBeDisabled()
  await expect(page.getByText('Approving needs the approver role.')).toBeVisible()

  // A different person, an approver, approves with a reason code and a confirmation step.
  await page.getByLabel('Acting as').selectOption('alice')
  await page.getByRole('button', { name: /Approve/ }).click()
  await page.getByLabel(/Reviewed; the plan is right as proposed/).check()
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Confirm approval' }).click()
  await expect(page.getByText(/Approved by alice/).first()).toBeVisible()

  await page.getByRole('link', { name: 'Audit trail' }).click()
  await expect(page.getByText('Decision recorded')).toBeVisible()
  await expect(page.getByText(/Intact:/)).toBeVisible()
})

test('the proposer cannot approve their own plan', async ({ page }) => {
  await actAs(page, 'bob')
  await page.goto('/')
  await page.getByRole('button', { name: /Re-plan exercise|Plan exercise/ }).click()
  await page.waitForURL(/\/plans\/\d+$/)
  await expect(page.getByText('Proposer cannot approve: you proposed this plan.')).toBeVisible()
  await expect(page.getByRole('button', { name: /Approve/ })).toBeDisabled()
})
