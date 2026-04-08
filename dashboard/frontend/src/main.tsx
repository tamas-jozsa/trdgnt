import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>,
)
