import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { axe, toHaveNoViolations } from 'jest-axe';
import PluginCard from '../PluginCard';
import { ThemeProvider } from '@/context/ThemeProvider';

expect.extend(toHaveNoViolations);

const mockPlugin = {
    id: '123',
    name: 'Accessible Plugin',
    description: 'Testing accessibility',
    database_type: 'postgresql',
    is_active: true,
    updated_at: '2023-01-01',
    tables: [],
    api_key_count: 0,
    session_count: 0
};

describe('PluginCard Accessibility', () => {
    it('should have no accessibility violations', async () => {
        const { container } = render(
            <ThemeProvider>
                <PluginCard plugin={mockPlugin} />
            </ThemeProvider>
        );

        const results = await axe(container);
        expect(results).toHaveNoViolations();
    });

    it('should have correct aria labels', () => {
        render(
            <ThemeProvider>
                <PluginCard plugin={mockPlugin} />
            </ThemeProvider>
        );

        expect(screen.getByRole('article')).toHaveAttribute('aria-labelledby', `plugin-name-${mockPlugin.id}`);
        expect(screen.getByLabelText('Status: Active')).toBeInTheDocument();
        expect(screen.getByLabelText('Edit Accessible Plugin')).toBeInTheDocument();
    });
});
