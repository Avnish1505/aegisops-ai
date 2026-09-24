import { useNavigate } from '@tanstack/react-router'
import { Command } from 'cmdk'
import { Dialog } from 'radix-ui'
import { useState } from 'react'
import { useDecisions, useExercise, useLabels, useStatus } from '../../api/queries'
import { SEVERITY_TEXT } from '../ui/SeverityGlyph'
import { AUTH_MODE, IDENTITIES, signIn, useIdentity } from '../../lib/auth'
import { useHotkeys } from '../../lib/hotkeys'
import { byPriority } from '../../lib/incidents'
import { applyTheme } from '../../lib/theme'
import { Kbd } from '../ui/Panel'

const ITEM = 'flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1 text-sm aria-selected:bg-bg aria-selected:shadow-[inset_2px_0_0_var(--focus)]'
const GROUP = '[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:text-muted'

export const SHORTCUTS: [string[], string][] = [
  [['J', 'K'], 'Next / previous item in the incident queue or report list'],
  [['Enter'], 'Open the selected incident’s plan, or edit the selected report'],
  [['A'], 'Approve (plan review; opens the confirmation dialog)'],
  [['R'], 'Reject (plan review; asks for a reason code)'],
  [['⌘', 'K'], 'Command palette (Ctrl+K on Windows and Linux)'],
  [['?'], 'This list of shortcuts'],
  [['Esc'], 'Close a dialog'],
]

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [help, setHelp] = useState(false)
  const navigate = useNavigate()
  const identity = useIdentity()
  const status = useStatus()
  const exercise = useExercise(identity ? status.data?.exercise?.id : undefined)
  const labels = useLabels(exercise.data).data
  const plans = useDecisions({ limit: 8 })

  useHotkeys({ 'mod+k': () => setOpen((current) => !current), '?': () => setHelp(true) })

  const go = (run: () => void) => {
    setOpen(false)
    run()
  }

  return (
    <>
      <Command.Dialog
        open={open}
        onOpenChange={setOpen}
        label="Command palette"
        overlayClassName="fixed inset-0 z-40 bg-black/50"
        contentClassName="fixed left-1/2 top-24 z-50 w-[36rem] max-w-[calc(100vw-2rem)] -translate-x-1/2 border border-control-border bg-raised text-text"
      >
        <Dialog.Title className="sr-only">Command palette</Dialog.Title>
        <Command.Input placeholder="Go to, open plan, find incident…" className="w-full border-b border-divider bg-transparent px-3 py-2 text-sm outline-none" />
        <Command.List className="max-h-96 overflow-auto p-1">
          <Command.Empty className="px-2 py-2 text-sm text-muted">Nothing matches.</Command.Empty>
          <Command.Group heading="Go to" className={GROUP}>
            <Command.Item className={ITEM} onSelect={() => go(() => void navigate({ to: '/' }))}>Operations board</Command.Item>
            <Command.Item className={ITEM} onSelect={() => go(() => void navigate({ to: '/triage' }))}>Intake triage</Command.Item>
            <Command.Item className={ITEM} onSelect={() => go(() => void navigate({ to: '/evals' }))}>Evaluations</Command.Item>
            <Command.Item className={ITEM} onSelect={() => go(() => setHelp(true))}>Keyboard shortcuts</Command.Item>
          </Command.Group>
          {plans.data && plans.data.length > 0 && (
            <Command.Group heading="Plans" className={GROUP}>
              {plans.data.map((plan) => (
                <Command.Item
                  key={plan.decision_id}
                  value={`plan ${plan.decision_id} ${plan.status}`}
                  className={ITEM}
                  onSelect={() => go(() => void navigate({ to: '/plans/$decisionId', params: { decisionId: plan.decision_id } }))}
                >
                  Plan <span className="font-mono">{plan.decision_id}</span>
                  <span className={plan.status === 'blocked' ? 'font-semibold text-blocked' : 'text-muted'}>
                    {plan.status === 'blocked' ? 'BLOCKED' : plan.disposition ? plan.disposition.action : 'awaiting approval'}
                  </span>
                </Command.Item>
              ))}
            </Command.Group>
          )}
          {exercise.data && (
            <Command.Group heading="Incidents" className={GROUP}>
              {byPriority(exercise.data.incidents, undefined).map((incident) => (
                <Command.Item
                  key={incident.id}
                  value={`${labels?.incidents[incident.id] ?? ''} ${incident.id} ${incident.severity} ${incident.type}`}
                  className={ITEM}
                  onSelect={() => go(() => void navigate({ to: '/', search: { incident: incident.id } }))}
                >
                  {labels?.incidents[incident.id] ?? 'Unnamed'}
                  <span className="font-mono text-muted">{incident.id}</span>
                  <span className="text-muted">{SEVERITY_TEXT[incident.severity]}</span>
                </Command.Item>
              ))}
            </Command.Group>
          )}
          {IDENTITIES[AUTH_MODE].length > 0 && (
            <Command.Group heading="Act as" className={GROUP}>
              {IDENTITIES[AUTH_MODE].map((option) => (
                <Command.Item key={option.sub} value={`act as ${option.label}`} className={ITEM} onSelect={() => go(() => signIn(option))}>
                  {option.label} {identity?.sub === option.sub && <span className="text-muted">(current)</span>}
                </Command.Item>
              ))}
            </Command.Group>
          )}
          <Command.Group heading="Theme" className={GROUP}>
            {(['system', 'dark', 'light'] as const).map((theme) => (
              <Command.Item key={theme} value={`theme ${theme}`} className={ITEM} onSelect={() => go(() => applyTheme(theme))}>
                Theme: {theme}
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>
      </Command.Dialog>
      <ShortcutSheet open={help} onOpenChange={setHelp} />
    </>
  )
}

function ShortcutSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content className="fixed left-1/2 top-24 z-50 w-[30rem] max-w-[calc(100vw-2rem)] -translate-x-1/2 space-y-3 border border-control-border bg-raised p-4 text-text">
          <Dialog.Title className="text-md font-semibold">Keyboard shortcuts</Dialog.Title>
          <Dialog.Description className="text-sm text-muted">Single keys work when no text field has focus.</Dialog.Description>
          <table className="w-full text-sm">
            <tbody>
              {SHORTCUTS.map(([keys, text]) => (
                <tr key={text} className="border-b border-divider">
                  <td className="w-24 py-1">{keys.map((key) => <Kbd key={key}>{key}</Kbd>)}</td>
                  <td className="py-1">{text}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Dialog.Close className="h-8 rounded border border-control-border bg-raised px-3 text-sm">Close</Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
