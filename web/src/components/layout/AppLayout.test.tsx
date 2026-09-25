import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AppLayout } from './AppLayout'

function renderAt(path: string) {
  const router = createMemoryRouter(
    [
      {
        path: '/',
        element: <AppLayout />,
        children: [
          { index: true, element: <p>conteúdo início</p> },
          { path: 'lancamentos', element: <p>conteúdo lançamentos</p> },
        ],
      },
    ],
    { initialEntries: [path] },
  )
  return render(<RouterProvider router={router} />)
}

describe('AppLayout', () => {
  it('renderiza menu principal e a rota filha', () => {
    renderAt('/lancamentos')
    const nav = screen.getByRole('navigation', { name: 'Menu principal' })
    expect(nav).toBeInTheDocument()
    expect(screen.getByText('conteúdo lançamentos')).toBeInTheDocument()
  })

  it('marca o item de menu ativo', () => {
    renderAt('/lancamentos')
    expect(screen.getByRole('link', { name: 'Lançamentos' })).toHaveClass('active')
    expect(screen.getByRole('link', { name: 'Início' })).not.toHaveClass('active')
  })
})
