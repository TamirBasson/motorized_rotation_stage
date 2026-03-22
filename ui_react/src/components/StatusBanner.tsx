import type { NotificationState } from "../types";

interface StatusBannerProps {
  notification: NotificationState;
  busy: boolean;
}

export function StatusBanner({ notification, busy }: StatusBannerProps) {
  return (
    <div className={`status-banner status-banner--${notification.level}`}>
      <div>
        <p className="status-banner__eyebrow">{busy ? "Command Queue Locked" : "System Status"}</p>
        <h3 className="status-banner__title">{notification.title}</h3>
        <p className="status-banner__message">{notification.message}</p>
      </div>
      <div className={`status-chip ${busy ? "status-chip--busy" : "status-chip--ready"}`}>
        {busy ? "Executing" : "Ready"}
      </div>
    </div>
  );
}
