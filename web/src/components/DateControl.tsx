import { shiftDate, todayIso, type IsoDate } from '../money.ts';
import { ChevronLeft, ChevronRight } from './Icons.tsx';

interface Props {
  value: IsoDate;
  onChange: (value: IsoDate) => void;
}

export function DateControl({ value, onChange }: Props) {
  const today = todayIso();
  return (
    <div className="date-control" role="group" aria-label="Дата отчёта">
      <button type="button" className="icon-button" onClick={() => onChange(shiftDate(value, -1))} aria-label="Предыдущий день">
        <ChevronLeft />
      </button>
      <label className="date-control__field">
        <span className="visually-hidden">Дата отчёта</span>
        <input
          type="date"
          value={value}
          required
          onChange={(event) => {
            if (event.target.value) onChange(event.target.value);
          }}
        />
      </label>
      <button type="button" className="icon-button" onClick={() => onChange(shiftDate(value, 1))} aria-label="Следующий день">
        <ChevronRight />
      </button>
      <button type="button" className="button button--quiet" onClick={() => onChange(today)} disabled={value === today}>
        Сегодня
      </button>
    </div>
  );
}
