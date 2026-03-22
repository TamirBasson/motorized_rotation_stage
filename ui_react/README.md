# React UI Structure

This folder contains a production-style React dashboard structure for the Motorized Rotation Stage Controller.

## Included Panels

- `Command Panel`: absolute move, relative move, zeroing, and stop
- `Telemetry Panel`: mechanical angle, virtual angle, speed, direction, state, and steps
- `System Configuration Panel`: steps per revolution, gear ratio, and virtual zero offset

## Design Intent

- dark-mode engineering dashboard
- large numeric readouts
- clear command isolation
- command lockout during execution
- stop remains available as the safety action
- status banner for warnings, errors, and execution feedback

## Main Files

- `src/App.tsx`
- `src/hooks/useStageDashboard.ts`
- `src/components/CommandPanel.tsx`
- `src/components/TelemetryPanel.tsx`
- `src/components/SystemConfigurationPanel.tsx`
- `src/styles.css`

## Integration Note

The current hook uses preview state only. In production, replace the preview command handlers with calls into the shared Communication Manager service so the UI never owns serial directly.
