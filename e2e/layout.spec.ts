import { actAs, expect, test } from './fixtures'

for (const theme of ['dark', 'light'] as const) {
  test(`Approve is visible without scrolling at 1440x900 (${theme})`, async ({ page }) => {
    await actAs(page, 'alice', theme)
    await page.goto('/plans/1')
    const approve = page.getByRole('button', { name: /Approve/ })
    await expect(approve).toBeVisible()
    const box = await approve.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.y + box!.height).toBeLessThanOrEqual(900)
    expect(box!.x + box!.width).toBeLessThanOrEqual(1440)
    expect(await page.evaluate(() => window.scrollY)).toBe(0)
    const width = await page.evaluate(() => document.documentElement.scrollWidth)
    expect(width).toBeLessThanOrEqual(1440)
  })
}
