import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Сборка кладётся в пакет Python: сервис отдаёт её сам, Node для запуска не нужен.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../advance_report/static',
    emptyOutDir: true,
  },
  server: {
    // npm run dev: интерфейс на :5173, отчёт — с запущенного python -m advance_report.
    proxy: { '/report': 'http://127.0.0.1:8000' },
  },
});
