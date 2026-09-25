import { createBrowserRouter, type RouteObject } from 'react-router-dom'

import { AppLayout } from './components/layout/AppLayout'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

export const routes: RouteObject[] = [
  { path: '/login', element: <PlaceholderPage title="Entrar" sprint="01" /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'lancamentos', element: <PlaceholderPage title="Lançamentos" sprint="02" /> },
      { path: 'upload', element: <PlaceholderPage title="Enviar comprovantes" sprint="03" /> },
      { path: 'relatorios', element: <PlaceholderPage title="Relatórios" sprint="09" /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
