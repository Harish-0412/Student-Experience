import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import {
  Award,
  CheckCircle2,
  Clock,
  HelpCircle,
  Play,
  X,
  XCircle,
} from 'lucide-react';

export const AssessmentsView = () => {
  const { selectedGoal, assessments, submitAssessment } = useApp();
  const [activeAssessment, setActiveAssessment] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const start = (assessment) => {
    setActiveAssessment(assessment);
    setQuestionIndex(0);
    setAnswers({});
    setResult(null);
  };

  const submit = async () => {
    setSubmitting(true);
    try {
      const attempt = await submitAssessment(activeAssessment, answers);
      setResult(attempt);
    } finally {
      setSubmitting(false);
    }
  };

  const close = () => {
    setActiveAssessment(null);
    setResult(null);
  };

  if (!selectedGoal) {
    return (
      <div className="mx-auto max-w-3xl py-20 text-center text-sm text-gray-500">
        Select a goal to view its published assessments.
      </div>
    );
  }

  const question = activeAssessment?.questions?.[questionIndex];
  const allAnswered =
    activeAssessment?.questions?.every((item) =>
      Object.hasOwn(answers, item.id),
    ) || false;

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <div>
        <h1 className="flex items-center gap-3 text-3xl font-extrabold text-white">
          <Award className="h-8 w-8 text-purple-400" />
          Assessments
        </h1>
        <p className="mt-2 text-sm text-gray-400">{selectedGoal.title}</p>
      </div>

      {assessments.length ? (
        <div className="divide-y divide-white/10 border-y border-white/10">
          {assessments.map((assessment) => (
            <div
              key={assessment.id}
              className="grid gap-4 py-6 md:grid-cols-[minmax(0,1fr)_180px_150px]"
            >
              <div>
                <div className="text-xs font-semibold uppercase text-purple-300">
                  {assessment.assessment_type} · {assessment.competency_ref}
                </div>
                <h2 className="mt-1 text-lg font-bold text-white">
                  {assessment.title}
                </h2>
                <p className="mt-2 text-xs text-gray-400">
                  {assessment.instructions}
                </p>
              </div>
              <div className="space-y-1 text-xs text-gray-400">
                <div className="flex items-center gap-2">
                  <HelpCircle className="h-3.5 w-3.5" />
                  {assessment.questions.length} questions
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-3.5 w-3.5" />
                  {assessment.time_limit_minutes
                    ? `${assessment.time_limit_minutes} minutes`
                    : 'No time limit'}
                </div>
                <div>{assessment.passing_percentage}% to pass</div>
              </div>
              <button
                type="button"
                onClick={() => start(assessment)}
                className="flex h-fit items-center justify-center gap-2 rounded-lg bg-purple-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-purple-500"
              >
                <Play className="h-3.5 w-3.5 fill-current" /> Start
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="border-y border-white/10 py-14 text-center text-sm text-gray-500">
          No published assessments are available for this goal.
        </div>
      )}

      {activeAssessment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/90 p-4 backdrop-blur-xl">
          <div className="w-full max-w-2xl rounded-2xl border border-white/15 bg-[#111116] p-7">
            {!result ? (
              <>
                <div className="mb-6 flex items-start justify-between border-b border-white/10 pb-4">
                  <div>
                    <p className="text-xs font-semibold uppercase text-purple-300">
                      {activeAssessment.assessment_type}
                    </p>
                    <h2 className="mt-1 text-xl font-bold text-white">
                      {activeAssessment.title}
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={close}
                    className="rounded-lg p-2 text-gray-400 hover:bg-white/10"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {question && (
                  <div className="space-y-5">
                    <div className="text-xs text-gray-500">
                      Question {questionIndex + 1} of{' '}
                      {activeAssessment.questions.length} · {question.points} points
                    </div>
                    <h3 className="text-base font-bold leading-relaxed text-white">
                      {question.prompt}
                    </h3>
                    <AnswerField
                      question={question}
                      value={answers[question.id]}
                      onChange={(value) =>
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: value,
                        }))
                      }
                    />
                  </div>
                )}

                <div className="mt-7 flex items-center justify-between border-t border-white/10 pt-4">
                  <button
                    type="button"
                    disabled={questionIndex === 0}
                    onClick={() => setQuestionIndex((value) => value - 1)}
                    className="rounded-lg border border-white/10 px-4 py-2 text-xs font-bold text-gray-300 disabled:opacity-40"
                  >
                    Previous
                  </button>
                  {questionIndex < activeAssessment.questions.length - 1 ? (
                    <button
                      type="button"
                      onClick={() => setQuestionIndex((value) => value + 1)}
                      className="rounded-lg bg-purple-600 px-5 py-2 text-xs font-bold text-white"
                    >
                      Next
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={!allAnswered || submitting}
                      onClick={submit}
                      className="rounded-lg bg-emerald-500 px-5 py-2 text-xs font-bold text-black disabled:opacity-50"
                    >
                      {submitting ? 'Scoring...' : 'Submit assessment'}
                    </button>
                  )}
                </div>
              </>
            ) : (
              <div className="space-y-6 py-3 text-center">
                {result.passed ? (
                  <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-400" />
                ) : (
                  <XCircle className="mx-auto h-12 w-12 text-rose-400" />
                )}
                <div>
                  <h2 className="text-2xl font-bold text-white">
                    {result.passed ? 'Assessment passed' : 'More practice needed'}
                  </h2>
                  <div className="mt-2 text-4xl font-extrabold text-purple-300">
                    {Math.round(result.percentage)}%
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    {result.score} / {result.max_score} points · attempt{' '}
                    {result.attempt_number}
                  </p>
                </div>
                {result.feedback.length > 0 && (
                  <div className="space-y-2 border-y border-white/10 py-4 text-left text-xs text-gray-300">
                    {result.feedback.map((item, index) => (
                      <p key={`${index}-${JSON.stringify(item)}`}>
                        {typeof item === 'string'
                          ? item
                          : item.feedback || item.message || JSON.stringify(item)}
                      </p>
                    ))}
                  </div>
                )}
                <button
                  type="button"
                  onClick={close}
                  className="w-full rounded-lg bg-purple-600 py-3 text-sm font-bold text-white"
                >
                  Return to assessments
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const AnswerField = ({ question, value, onChange }) => {
  if (question.options.length > 0) {
    return (
      <div className="space-y-2">
        {question.options.map((option) => (
          <button
            type="button"
            key={option}
            onClick={() => onChange(option)}
            className={`w-full rounded-lg border p-4 text-left text-sm ${
              value === option
                ? 'border-purple-500 bg-purple-500/15 text-purple-100'
                : 'border-white/10 bg-white/5 text-gray-300 hover:bg-white/10'
            }`}
          >
            {option}
          </button>
        ))}
      </div>
    );
  }
  if (question.kind === 'boolean' || question.kind === 'true_false') {
    return (
      <div className="flex gap-2">
        {[true, false].map((option) => (
          <button
            type="button"
            key={String(option)}
            onClick={() => onChange(option)}
            className={`rounded-lg border px-5 py-3 text-sm font-bold ${
              value === option
                ? 'border-purple-500 bg-purple-500/15 text-purple-100'
                : 'border-white/10 text-gray-300'
            }`}
          >
            {String(option)}
          </button>
        ))}
      </div>
    );
  }
  return (
    <textarea
      value={value || ''}
      onChange={(event) => onChange(event.target.value)}
      rows={5}
      className="w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
    />
  );
};
