import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, test } from 'vitest'
import { AppRoutes } from '../App'
import { SessionProvider } from '../session'

const reportText = () => within(screen.getByRole('region', { name: /^Report \d/ }))

const renderAt = (path: string) => render(
  <SessionProvider><MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter></SessionProvider>,
)

test('sample patient → results → ask across all reports → citation switches report', async () => {
  const user = userEvent.setup()
  renderAt('/upload')
  await user.click(screen.getByRole('button', { name: 'Try a sample patient (5 reports)' }))

  expect(await screen.findByRole('heading', { level: 1, name: /Report 1/ })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Ask across all 5 reports' })).toHaveAttribute('aria-selected', 'true')
  expect(await screen.findByRole('table', { name: 'Findings over time' })).toBeInTheDocument()

  // Clicking a finding highlights its evidence.
  await user.click(screen.getByRole('button', { name: /Cardiomegaly/ }))
  expect(reportText().getByText('Heart size is normal.').closest('li')).toHaveClass('bg-hl')

  await user.type(screen.getByLabelText('Your question'), 'How did the pleural effusion change?')
  await user.click(screen.getByRole('button', { name: 'Ask' }))
  expect(await screen.findByText(/stayed moderate in report 3/)).toBeInTheDocument()
  expect(screen.getByText('Retrieved 6 sentences from 5 reports')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Show report 3, sentence F2' }))
  expect(screen.getByRole('heading', { level: 1, name: /Report 3/ })).toBeInTheDocument()
  expect(reportText().getByText('Moderate left pleural effusion, unchanged.').closest('li')).toHaveClass('bg-hl')
  expect(screen.getByText(/citation Report 3 · F2/)).toBeInTheDocument()
})

test('ask about one report, and refusals', async () => {
  const user = userEvent.setup()
  renderAt('/upload')
  await user.click(screen.getByRole('button', { name: 'Try a sample patient (5 reports)' }))
  await screen.findByRole('heading', { level: 1, name: /Report 1/ })

  await user.selectOptions(screen.getByLabelText('Report'), 'Report 3 of 5')
  await user.click(screen.getByRole('tab', { name: 'Ask about this report' }))
  await user.click(screen.getByRole('button', { name: 'Is the pacemaker in the right place?' }))
  expect(await screen.findByText('The report describes the leads in expected position.')).toBeInTheDocument()

  await user.click(screen.getByRole('tab', { name: 'Ask across all 5 reports' }))
  await user.type(screen.getByLabelText('Your question'), 'Should the patient start antibiotics?{Enter}')
  expect(await screen.findByText(/not give treatment advice/)).toBeInTheDocument()
})

test('upload needs content and the confirmation; mock mode shows an error for own reports', async () => {
  const user = userEvent.setup()
  renderAt('/upload')
  await user.click(screen.getByRole('button', { name: 'Analyze reports' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Paste a report or add at least one file.')

  await user.type(screen.getByLabelText('Paste a report'), 'FINDINGS: No pneumothorax.')
  await user.click(screen.getByRole('button', { name: 'Analyze reports' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Please confirm')

  await user.click(screen.getByLabelText(/I confirm/))
  await user.click(screen.getByRole('button', { name: 'Analyze reports' }))
  const alert = await screen.findByRole('alert')
  expect(within(alert).getByRole('heading')).toHaveTextContent("We couldn't analyze your reports")
  expect(within(alert).getByRole('button', { name: 'Try again' })).toBeInTheDocument()
})

test('landing renders, no social links', () => {
  renderAt('/')
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Radiology reports,explained with evidence.')
  expect(screen.queryByText(/linkedin/i)).toBeNull()
})

test('results without a session redirect to upload', () => {
  renderAt('/results')
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Turn chest X-ray reports into verified findings')
})
