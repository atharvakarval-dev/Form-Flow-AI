import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PluginCard from '../PluginCard';
import { ThemeProvider } from '@/context/ThemeProvider';

// Mock ThemeProvider
const MockThemeProvider = ({ children }) => (
    // Mock contexts if needed, here just basic render
    <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
        {children}
    </ThemeProvider>
);

const mockPlugin = {
    id: '123',
    name: 'Test Plugin',
    description: 'This is a test plugin',
    database_type: 'postgresql',
    is_active: true,
    updated_at: '2023-01-01T00:00:00Z',
    tables: [{}, {}],
    api_key_count: 5,
    session_count: 100
};

describe('PluginCard Component', () => {
    it('renders plugin information correctly', () => {
        render(
            <MockThemeProvider>
                <PluginCard plugin={mockPlugin} />
            </MockThemeProvider>
        );

        expect(screen.getByText('Test Plugin')).toBeInTheDocument();
        expect(screen.getByText('This is a test plugin')).toBeInTheDocument();
        expect(screen.getByText('postgresql')).toBeInTheDocument();
        expect(screen.getByText('Active')).toBeInTheDocument();
        expect(screen.getByText('2 tables')).toBeInTheDocument();
        expect(screen.getByText('5 keys')).toBeInTheDocument();
    });

    it('calls action handlers when buttons are clicked', () => {
        const onEdit = vi.fn();
        const onAPIKeys = vi.fn();
        const onDelete = vi.fn();

        render(
            <MockThemeProvider>
                <PluginCard
                    plugin={mockPlugin}
                    onEdit={onEdit}
                    onAPIKeys={onAPIKeys}
                    onDelete={onDelete}
                />
            </MockThemeProvider>
        );

        fireEvent.click(screen.getByLabelText('Edit Test Plugin'));
        expect(onEdit).toHaveBeenCalledWith(mockPlugin);

        fireEvent.click(screen.getByLabelText('Manage API keys for Test Plugin'));
        expect(onAPIKeys).toHaveBeenCalledWith(mockPlugin);

        fireEvent.click(screen.getByLabelText('Delete Test Plugin'));
        expect(onDelete).toHaveBeenCalledWith(mockPlugin);
    });

    it('renders inactive status correctly', () => {
        const inactivePlugin = { ...mockPlugin, is_active: false };
        render(
            <MockThemeProvider>
                <PluginCard plugin={inactivePlugin} />
            </MockThemeProvider>
        );

        expect(screen.getByText('Inactive')).toBeInTheDocument();
    });
});
