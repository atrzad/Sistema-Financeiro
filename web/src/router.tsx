import { createBrowserRouter, type RouteObject } from 'react-router-dom'

import { AppLayout } from './components/layout/AppLayout'
import { LoginPage } from './features/auth/LoginPage'
import { ProtectedRoute } from './features/auth/ProtectedRoute'
import { UsersPage } from './features/users/UsersPage'
import { CadastrosPage } from './features/cadastros/CadastrosPage'
import { FornecedoresPage } from './features/fornecedores/FornecedoresPage'
import { LancamentoFormPage } from './features/lancamentos/LancamentoFormPage'
import { LancamentosPage } from './features/lancamentos/LancamentosPage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <HomePage /> },
      { path: 'lancamentos', element: <LancamentosPage /> },
      { path: 'lancamentos/novo', element: <LancamentoFormPage /> },
      { path: 'lancamentos/:id', element: <LancamentoFormPage /> },
      { path: 'fornecedores', element: <FornecedoresPage /> },
      {
        path: 'cadastros',
        element: (
          <ProtectedRoute roles={['admin']}>
            <CadastrosPage />
          </ProtectedRoute>
        ),
      },
      { path: 'upload', element: <PlaceholderPage title="Enviar comprovantes" sprint="03" /> },
      { path: 'relatorios', element: <PlaceholderPage title="Relatórios" sprint="09" /> },
      {
        path: 'usuarios',
        element: (
          <ProtectedRoute roles={['admin']}>
            <UsersPage />
          </ProtectedRoute>
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
