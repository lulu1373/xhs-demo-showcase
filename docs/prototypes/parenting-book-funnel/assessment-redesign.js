const QUESTIONS = [
  "我对自己的教养能力有信心。",
  "面对孩子的不当行为时，我知道该怎么处理。",
  "亲子关系紧张时，我相信自己能慢慢改善。",
  "遇到新的教养问题时，我能边学边调整。",
  "我相信向孩子解释规则理由，会提升他的配合度。",
  "我相信和孩子沟通说理，有助于改善问题。",
  "我相信解释行为后果，能帮助孩子慢慢改变。",
  "我相信清楚表达感受和规则，会帮助孩子理解行为边界。",
  "我稳定自身情绪，能缓和亲子间的矛盾冲突。",
  "即使孩子没有按期待变化，我也能继续坚持。",
  "即使孩子因为管教而不高兴，我也能坚持该有的做法。",
  "即使同样的问题反复出现，我也能继续按原定方式处理。",
  "我认为家长需要考虑孩子的感受和意愿。",
  "我认同孩子可以有不同于家长的想法。",
  "我认为家长需要尊重孩子表达意见。",
  "我认为家长核心价值，是引导孩子成长与自律。"
];

const OPTIONS = [
  { value: 1, label: "非常不同意" },
  { value: 2, label: "不同意" },
  { value: 3, label: "不确定" },
  { value: 4, label: "同意" },
  { value: 5, label: "非常同意" }
];

function renderQuestions() {
  const list = document.querySelector("[data-question-list]");
  if (!list) return;

  list.innerHTML = QUESTIONS.map((question, index) => {
    const id = `q${index + 1}`;
    const options = OPTIONS.map(
      (option) => `
        <label class="option">
          <input type="radio" name="${id}" value="${option.value}">
          <span class="option__dot"></span>
          <span>${option.label}</span>
        </label>
      `
    ).join("");

    return `
      <article class="card question-card" data-question-id="${id}">
        <h2 class="question-card__title">${index + 1}. ${question}</h2>
        <div class="option-grid">
          ${options}
        </div>
      </article>
    `;
  }).join("");

  list.addEventListener("change", updateProgress);
  updateProgress();
}

function updateProgress() {
  const fill = document.querySelector("[data-progress-fill]");
  const meta = document.querySelector("[data-progress-meta]");
  const hint = document.querySelector("[data-progress-hint]");
  const action = document.querySelector("[data-progress-action]");
  const firstMissing = [...QUESTIONS.keys()].find(
    (index) => !document.querySelector(`input[name="q${index + 1}"]:checked`)
  );
  const answered = QUESTIONS.length - (firstMissing === undefined
    ? 0
    : [...QUESTIONS.keys()].filter((index) => !document.querySelector(`input[name="q${index + 1}"]:checked`)).length);
  const progress = Math.round((answered / QUESTIONS.length) * 100);

  if (fill) fill.style.width = `${progress}%`;
  if (meta) meta.textContent = `已完成 ${answered} / ${QUESTIONS.length}`;

  const missingCount = QUESTIONS.length - answered;
  if (hint) {
    hint.textContent = missingCount > 0
      ? `还有 ${missingCount} 题未完成`
      : "已完成全部题目，可以查看结果";
  }

  if (action) {
    action.disabled = missingCount > 0;
    action.textContent = missingCount > 0 ? "查看结果" : "查看结果";
    action.onclick = () => {
      if (missingCount > 0) {
        const missingCard = document.querySelector(
          `[data-question-id="q${firstMissing + 1}"]`
        );
        if (missingCard) {
          missingCard.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        return;
      }
      window.location.href = "assessment-results-redesign.html";
    };
  }
}

document.addEventListener("DOMContentLoaded", renderQuestions);
