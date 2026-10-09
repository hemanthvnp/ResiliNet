import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';

// Cytoscape needs canvas/DOM measurements which jsdom doesn't fully implement
vi.mock('cytoscape', () => {
  return {
    default: vi.fn(() => ({
      on: vi.fn(),
      destroy: vi.fn(),
      elements: vi.fn(() => ({
        style: vi.fn(),
      })),
    })),
  };
});

describe('App Component (Task 1.2)', () => {
  it('renders the ResiliNet application header and main dashboard', async () => {
    const { findByText, findByTestId } = render(<App />);

    expect(await findByText('ResiliNet')).toBeInTheDocument();
    expect(await findByText(/Campus Network Rerouter/i)).toBeInTheDocument();
    expect(await findByTestId('app-root')).toBeInTheDocument();
    expect(await findByTestId('baseline-panel')).toBeInTheDocument();
    expect(await findByTestId('s2-panel')).toBeInTheDocument();
    expect(await findByTestId('flow-table')).toBeInTheDocument();
  });
});
