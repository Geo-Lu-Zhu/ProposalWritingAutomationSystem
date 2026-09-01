import { ref } from "vue";
import { api } from "../api";

const POLL_INTERVAL_MS = 1500;

/**
 * Polls GET /jobs/{id} until the job reaches done|error.
 * Returns reactive state plus a `watch(jobId)` function to start polling.
 */
export function useJobPolling() {
  const status = ref(null); // "queued" | "running" | "done" | "error"
  const progress = ref({});
  const result = ref(null);
  const error = ref(null);

  let timer = null;

  function stop() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function watchJob(jobId) {
    stop();
    status.value = "queued";
    progress.value = {};
    result.value = null;
    error.value = null;

    const poll = async () => {
      try {
        const job = await api.getJob(jobId);
        status.value = job.status;
        progress.value = job.progress || {};

        if (job.status === "done") {
          result.value = job.result;
          return;
        }
        if (job.status === "error") {
          error.value = job.error;
          return;
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (e) {
        status.value = "error";
        error.value = e.message;
      }
    };

    poll();
  }

  return { status, progress, result, error, watchJob, stop };
}
