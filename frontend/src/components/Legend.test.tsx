import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Legend } from './Legend';

describe('Legend (Task 5.3)', () => {
  it('names every link state the graph draws, with its text cue', () => {
    render(<Legend />);

    expect(screen.getByText(/0% → 100%/)).toBeInTheDocument();
    expect(screen.getByText(/above 100%/)).toBeInTheDocument();
    expect(screen.getByText(/labelled DOWN/)).toBeInTheDocument();
  });
});
