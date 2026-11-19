import type { ReactNode } from 'react';

import type { PaymentLine, WorkLine } from '../api.ts';
import { formatDate } from '../money.ts';

type Tone = 'done' | 'planned' | 'cancelled' | 'queued' | 'refunded';

function Badge({ tone, children, note }: { tone: Tone; children: ReactNode; note?: ReactNode }) {
  return (
    <span className={`status status--${tone}`}>
      <span className="status__dot" aria-hidden="true" />
      <span className="status__text">{children}</span>
      {note && <span className="status__note">{note}</span>}
    </span>
  );
}

export function WorkStatus({ work }: { work: WorkLine }) {
  switch (work.status) {
    case 'done':
      return <Badge tone="done">Принята {formatDate(work.status_date!)}</Badge>;
    case 'cancelled':
      return <Badge tone="cancelled">Отменена {formatDate(work.status_date!)}</Badge>;
    case 'planned':
      return <Badge tone="planned">Запланирована</Badge>;
  }
}

export function PaymentStatus({ payment }: { payment: PaymentLine }) {
  switch (payment.status) {
    case 'paid':
      return <Badge tone="done">Оплачен {formatDate(payment.paid_at!)}</Badge>;
    case 'refunded':
      return (
        <Badge tone="refunded" note={`(оплачен ${formatDate(payment.paid_at!)})`}>
          Возвращён {formatDate(payment.refunded_at!)}
        </Badge>
      );
    case 'queued':
      return <Badge tone="queued">В очереди с {formatDate(payment.created_at)}</Badge>;
  }
}
