class RememberTheMilkCard extends HTMLElement {
  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `
        <ha-card header="Remember The Milk">
          <div class="card-content" style="display: flex; gap: 15px;">
            <div id="task-lists" style="flex: 1; padding-right: 10px; border-right: 1px solid #ccc;">
              <strong>Task Lists:</strong>
              <ul id="task-list-container" style="padding: 0;"></ul>
            </div>
            <div id="task-items" style="flex: 2; padding-left: 10px;">
              <div id="add-task" style="margin-bottom: 15px;">
                <input id="new-task-name" placeholder="New Task Name" type="text" style="padding: 5px; width: calc(100% - 80px);" />
                <button id="add-task-btn" style="padding: 5px 10px; margin-top: 5px;">Add Task</button>
              </div>
              <div id="tasks"></div>
              <div id="completed-tasks"></div>
              <div id="pagination" style="text-align: center; margin-top: 10px;">
                <button id="prev-page" style="margin-right: 10px;" disabled>Previous</button>
                <span id="page-number">Page 1</span>
                <button id="next-page" style="margin-left: 10px;" disabled>Next</button>
              </div>
            </div>
          </div>
          <img src="https://i.imgur.com/BSnlLW8.png" alt="Logo" style="position: absolute; top: 10px; right: 10px; height: 40px;">
        </ha-card>
      `;
      this.taskListsContainer = this.querySelector("#task-lists");
      this.taskItemsContainer = this.querySelector("#tasks");
      this.completedTasksContainer = this.querySelector("#completed-tasks");
      this.paginationContainer = this.querySelector("#pagination");
      this.pageNumberElement = this.querySelector("#page-number");
      this.prevButton = this.querySelector("#prev-page");
      this.nextButton = this.querySelector("#next-page");
      this.addTaskContainer = this.querySelector("#add-task");
    }

    const entityId = this.config.entity;
    const entityState = hass.states[entityId];
    if (!entityState) {
      this.taskListsContainer.innerHTML = `<p>Entity ${entityId} not found.</p>`;
      return;
    }

    const attributes = entityState.attributes;
    const taskLists = attributes.task_lists || [];
    const taskItems = attributes.items || [];
    const selectedTaskListId = entityState.state || "None";

    const tasksPerPage = 5;
    let currentPage = 1;

    const totalPages = Math.ceil(taskItems.length / tasksPerPage);

    const displayTasks = (page) => {
      const startIdx = (page - 1) * tasksPerPage;
      const endIdx = page * tasksPerPage;
      const tasksToDisplay = taskItems.slice(startIdx, endIdx);

      const uncompletedTasks = tasksToDisplay.filter(
        (task) => task.status !== "completed"
      );
      const completedTasks = tasksToDisplay.filter(
        (task) => task.status === "completed"
      );

      this.taskItemsContainer.innerHTML = `
        <strong>Tasks:</strong>
        <div>
          ${uncompletedTasks
            .map(
              (task) => `
              <div style="display: flex; align-items: center; margin-bottom: 10px; padding: 10px; background: #f9f9f9; border: 1px solid #ccc; border-radius: 5px; max-width: 90%;">
                <input type="checkbox" data-task-id="${
                  task.uid
                }" class="status-toggle" />
                <div style="display: flex; flex: 1; justify-content: space-between; align-items: center;">
                  <span style="font-weight: bold; margin-right: 8px; font-size: 10px;">${
                    task.summary
                  }</span>
                  ${
                    task.due
                      ? `<span style="background: #ffdddd; color: #d32f2f; font-size: 10px; padding: 1px 3px; border-radius: 3px; white-space: nowrap;">
                          ${new Date(task.due).toLocaleString("en-GB", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>`
                      : ""
                  }
                  <button data-task-id="${task.uid}" class="delete-task-btn"
                    style="margin-left: 10px; background: none; border: none; color: red; font-size: 18px; cursor: pointer;">
                    ×
                  </button>
                </div>
              </div>
            `
            )
            .join("")}
        </div>
      `;

      this.completedTasksContainer.innerHTML = `
        <strong>Completed:</strong>
        <div>
          ${completedTasks
            .map(
              (task) => `
              <div style="display: flex; align-items: center; margin-bottom: 10px; padding: 10px; background: #f1f8e9; border: 1px solid #ccc; border-radius: 5px; max-width: 90%;">
                <input type="checkbox" data-task-id="${
                  task.uid
                }" class="status-toggle" checked />
                <div style="display: flex; flex: 1; justify-content: space-between; align-items: center;">
                  <span style="font-weight: bold; margin-right: 8px; font-size: 10px; text-decoration: line-through;">${
                    task.summary
                  }</span>
                  ${
                    task.due
                      ? `<span style="background: #e8f5e9; color: #4caf50; font-size: 10px; padding: 1px 3px; border-radius: 3px; white-space: nowrap;">
                          ${new Date(task.due).toLocaleString("en-GB", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>`
                      : ""
                  }
                  <button data-task-id="${task.uid}" class="delete-task-btn"
                    style="margin-left: 10px; background: none; border: none; color: red; font-size: 18px; cursor: pointer;">
                    ×
                  </button>
                </div>
              </div>
            `
            )
            .join("")}
        </div>
      `;

      this.pageNumberElement.textContent = `Page ${page}`;
      this.prevButton.disabled = page === 1;
      this.nextButton.disabled = page === totalPages;
    };

    displayTasks(currentPage);

    this.prevButton.addEventListener("click", () => {
      if (currentPage > 1) {
        currentPage--;
        displayTasks(currentPage);
      }
    });

    this.nextButton.addEventListener("click", () => {
      if (currentPage < totalPages) {
        currentPage++;
        displayTasks(currentPage);
      }
    });

    // Event listener for toggling task completion
    const handleTaskStatusChange = async (event) => {
      if (event.target.classList.contains("status-toggle")) {
        const taskUid = event.target.dataset.taskId;
        const isChecked = event.target.checked;

        const [taskseriesId, taskId] = taskUid.split("_");
        const payload = {
          list_id: selectedTaskListId,
          taskseries_id: taskseriesId,
          task_id: taskId,
        };

        try {
          if (isChecked) {
            await hass
              .callService("remember_the_milk", "rtm_method", {
                method: "rtm.tasks.complete",
                payload: JSON.stringify(payload),
              })
              .then(() =>
                hass.callService("homeassistant", "update_entity", {
                  entity_id: this.config.entity,
                })
              );
          } else {
            await hass
              .callService("remember_the_milk", "rtm_method", {
                method: "rtm.tasks.uncomplete",
                payload: JSON.stringify(payload),
              })
              .then(() =>
                hass.callService("homeassistant", "update_entity", {
                  entity_id: this.config.entity,
                })
              );
          }
          alert("Task status updated successfully!");
        } catch (error) {
          alert(`Error updating task status: ${error.message}`);
        }
      }
    };
    this.taskItemsContainer.addEventListener("change", handleTaskStatusChange);
    this.completedTasksContainer.addEventListener(
      "change",
      handleTaskStatusChange
    );

    // Display All The Task Lists in the left section
    this.taskListsContainer.innerHTML = `
      <strong>Task Lists:</strong>
      <ul style="padding: 0;">
        ${taskLists
          .map(
            (list) => `
          <li style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
            <button
              data-task-list-id="${list.id}"
              class="task-list-btn"
              style="
                padding: 5px 10px;
                border-radius: 5px;
                border: ${
                  list.id === selectedTaskListId
                    ? "2px solid #43b7f9;"
                    : "1px solid gray;"
                };
                background: ${
                  list.id === selectedTaskListId ? "#e0f0ff;" : "transparent;"
                };
                font-weight: ${
                  list.id === selectedTaskListId ? "bold;" : "normal;"
                };
                cursor: pointer;
              "
            >
              ${list.name}
            </button>
            ${
              list.name !== "Inbox" && list.name !== "Sent"
                ? `
                <button
                  data-task-list-id="${list.id}"
                  class="delete-task-list-btn"
                  title="Delete List"
                  style="background: none; border: none; color: red; font-size: 18px; cursor: pointer;"
                >
                  ×
                </button>
              `
                : ""
            }
          </li>
        `
          )
          .join("")}
      </ul>
    `;

    // Delete Task List functionality for lists other than inbox and sent
    this.taskListsContainer
      .querySelectorAll(".delete-task-list-btn")
      .forEach((btn) => {
        btn.addEventListener("click", async (event) => {
          const listId = event.target.dataset.taskListId;

          if (!confirm("Are you sure you want to delete this task list?"))
            return;

          try {
            await hass
              .callService("remember_the_milk", "rtm_method", {
                method: "rtm.lists.delete",
                payload: JSON.stringify({ list_id: listId }),
              })
              .then(() =>
                hass.callService("homeassistant", "update_entity", {
                  entity_id: this.config.entity,
                })
              );
            alert("Task list deleted successfully!");
          } catch (error) {
            console.error("Failed to delete task list:", error);
            alert(`Error deleting task list: ${error.message}`);
          }
        });
      });

    // Delete individual task functionality
    this.taskItemsContainer.addEventListener("click", async (event) => {
      if (event.target.classList.contains("delete-task-btn")) {
        const taskUid = event.target.dataset.taskId;
        const [taskseriesId, taskId] = taskUid.split("_");

        const payload = {
          list_id: selectedTaskListId,
          taskseries_id: taskseriesId,
          task_id: taskId,
        };
        try {
          await hass
            .callService("remember_the_milk", "rtm_method", {
              method: "rtm.tasks.delete",
              payload: JSON.stringify(payload),
            })
            .then(() =>
              hass.callService("homeassistant", "update_entity", {
                entity_id: this.config.entity,
              })
            );
          alert("Task deleted successfully!");
        } catch (error) {
          alert(`Error deleting task: ${error.message}`);
        }
      }
    });

    // Add Task button click handler
    const addTaskButton = this.querySelector("#add-task-btn");
    if (addTaskButton) {
      addTaskButton.addEventListener("click", async () => {
        const taskNameInput = this.querySelector("#new-task-name");

        const taskName = taskNameInput.value.trim();
        if (!taskName) {
          alert("Task name cannot be empty!");
          return;
        }
        const payload = {
          list_id: selectedTaskListId,
          name: taskName,
        };

        try {
          await hass
            .callService("remember_the_milk", "rtm_method", {
              method: "rtm.tasks.add",
              payload: JSON.stringify(payload),
            })
            .then(() =>
              hass.callService("homeassistant", "update_entity", {
                entity_id: this.config.entity,
              })
            );
          alert("Task added successfully!");
        } catch (error) {
          alert(`Error adding task: ${error.message}`);
        }
        taskNameInput.value = "";
      });
    }

    // Attach click event listeners for task list selection
    this.taskListsContainer
      .querySelectorAll(".task-list-btn")
      .forEach((btn) => {
        btn.addEventListener("click", (event) => {
          const listId = event.target.dataset.taskListId;
          hass.callService("remember_the_milk", "update_task_list", {
            list_id: listId,
          });
        });
      });
  }

  setConfig(config) {
    this.config = config;
  }

  getCardSize() {
    return 3;
  }
}

customElements.define("remember-the-milk-card", RememberTheMilkCard);
