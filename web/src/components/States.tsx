import type { ReportError } from '../api.ts';
import { formatDate, type IsoDate } from '../money.ts';
import { Alert } from './Icons.tsx';

export function LoadingState() {
  return (
    <div className="skeleton" aria-hidden="true">
      <div className="summary">
        <div className="summary__intro">
          <span className="skeleton__line skeleton__line--short" />
          <span className="skeleton__line skeleton__line--display" />
          <span className="skeleton__line" />
          <span className="skeleton__line skeleton__line--mid" />
        </div>
        <div className="skeleton__block" />
      </div>
      <div className="skeleton__block skeleton__block--tall" />
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ReportError; onRetry: () => void }) {
  const hint = {
    offline: 'Запустите сервис командой python -m advance_report в папке проекта и повторите.',
    data: 'Исправьте строки в CSV-файлах папки data/ — сервис перечитает их при следующем запросе.',
    request: 'Проверьте дату отчёта.',
  }[error.kind];

  return (
    <section className="state state--error" role="alert">
      <Alert className="state__icon" />
      <h1 className="state__title">{error.kind === 'data' ? 'В выгрузке есть ошибки — отчёт не построен' : error.message}</h1>
      <p className="state__text">{hint}</p>
      {error.problems.length > 0 && (
        <ol className="problems">
          {error.problems.map((problem) => <li key={problem}>{problem}</li>)}
        </ol>
      )}
      <button type="button" className="button" onClick={onRetry}>Повторить</button>
    </section>
  );
}

export function EmptyState({ date }: { date: IsoDate }) {
  return (
    <section className="state">
      <h1 className="state__title">На {formatDate(date)} ещё нет подписанных договоров</h1>
      <p className="state__text">Отчёт показывает договоры, подписанные не позже даты отчёта. Выберите дату позже.</p>
    </section>
  );
}
