import clsx from 'clsx';

const severityStyles = {
  critical: 'badge-critical',
  high: 'badge-high',
  medium: 'badge-medium',
  low: 'badge-low',
  info: 'badge-info',
};

export default function SeverityBadge({ severity }) {
  return (
    <span className={clsx('badge capitalize', severityStyles[severity] || 'badge-info')}>
      {severity}
    </span>
  );
}

export function StatusBadge({ status }) {
  const styles = {
    new: 'bg-blue-900/50 text-blue-300',
    seen: 'bg-gray-700 text-gray-300',
    in_progress: 'bg-yellow-900/50 text-yellow-300',
    discarded: 'bg-gray-800 text-gray-500',
    escalated: 'bg-orange-900/50 text-orange-300',
    closed: 'bg-green-900/50 text-green-300',
  };
  return (
    <span className={clsx('badge', styles[status] || 'badge-info')}>
      {status?.replace('_', ' ')}
    </span>
  );
}
