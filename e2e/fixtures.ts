import AxeBuilder from '@axe-core/playwright'
import { test as base, expect, type Page } from '@playwright/test'

export type Identity = 'olive' | 'alice' | 'bob'

/** Every test fails if the page logs a console error or throws. */
export const test = base.extend<{ consoleErrors: string[] }>({
  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = []
      page.on('console', (message) => {
        if (message.type() === 'error') errors.push(message.text())
      })
      page.on('pageerror', (error) => errors.push(String(error)))
      await use(errors)
      expect(errors, 'console errors').toEqual([])
    },
    { auto: true },
  ],
})

export { expect }

/** Sign in as a dev identity (and optionally pin the theme) before the app loads. */
export async function actAs(page: Page, sub: Identity, theme?: 'dark' | 'light'): Promise<void> {
  await page.addInitScript(
    ([identity, chosen]) => {
      window.localStorage.setItem('aegisops.identity', identity)
      if (chosen) window.localStorage.setItem('aegisops.theme', chosen)
    },
    [sub, theme ?? ''] as const,
  )
}

export async function axe(page: Page) {
  return new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
}
