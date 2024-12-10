# Remember The Milk Integration for Home Assistant

## Overview

The **Remember The Milk Integration** for Home Assistant enables users to manage tasks from their Remember The Milk accounts directly within Home Assistant. This integration supports creating, updating, completing, and deleting tasks and task lists while providing real-time updates through Home Assistant's interface.

### Features

- Synchronize tasks from Remember The Milk with Home Assistant.
- Create, update, complete, and delete tasks and task lists.
- Notifications for upcoming due tasks.
- Intuitive UI card for task management.
- Drag to change priority.
- Detect duplicate tasks and lists.
- Task statistics for better task tracking.

---

## Installation

### Prerequisites

1. **Home Assistant** installed and running.
2. A Remember The Milk account.
3. API Key and Shared Secret from the [Remember The Milk API page](https://www.rememberthemilk.com/services/api/).

### Setup Steps

1. Clone or download this repository.

  ```bash
  git clone https://github.com/amalte/core.git
  ```

2. Copy the `remember_the_milk` folder to your Home Assistant `components` directory:

  ```
  core/homeassistant/components/remember_the_milk
  ```

3. Restart Home Assistant.

---

## Configuration

### Configuration in `configuration.yaml`

Add the following configuration to your `configuration.yaml` file:

```yaml
remember_the_milk:
  - name: "MyRTMAccount"
    api_key: "<YOUR_API_KEY>"
    shared_secret: "<YOUR_SHARED_SECRET>"
```

### Example Configuration

```yaml
remember_the_milk:
  - name: "Work"
    api_key: "your_api_key_here"
    shared_secret: "your_shared_secret_here"
```

Restart Home Assistant after editing the configuration file.

---

## Usage

### Services

The integration provides the following services:

- **`remember_the_milk.create_task`**: Create a new task.
- **`remember_the_milk.complete_task`**: Mark a task as completed.
- **`remember_the_milk.update_task_list`**: Update a task list.
- **`remember_the_milk.rtm_method`**: Execute custom Remember The Milk API methods.

### Example Service Call

#### Creating a Task

Service: `remember_the_milk.create_task`

```yaml
service: remember_the_milk.create_task
data:
  name: "Buy Groceries"
```

#### Completing a Task

Service: `remember_the_milk.complete_task`

```yaml
service: remember_the_milk.complete_task
data:
  id: "task_id_here"
```

---

## Custom UI Card

The integration includes a custom UI card to manage tasks.

### Steps to Add the Custom Card

1. Copy the `remember-the-milk-card.js` file to the `<config_directory>/www/` directory.

2. In Home Assistant, go to **Overview** -> **Manage Dashboard** -> **Resources** -> **Add Resource**.

3. Add the following URL as the resource:

  ```bash
  /local/remember-the-milk-card.js
  ```

4. Restart Home Assistant.

5. Add the manual card to your Lovelace dashboard with the following configuration:

  ```yaml
  views: null
  title: Remember The Milk
  path: remember-the-milk
  cards: null
  type: custom:remember-the-milk-card
  entity: sensor.rememberthemilk_sensor
  ```


---

## Notifications

The integration sends persistent notifications for tasks due within the next hour.

---

## Statistics

View task statistics directly from the custom UI card, including:

- Tasks completed today.
- Total tasks due today.
- Total completed tasks.