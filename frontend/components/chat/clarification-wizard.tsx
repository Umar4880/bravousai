"use client";

import React, { useState, useEffect } from "react";
import type { ClarificationQuestion } from "./types";

interface ClarificationWizardProps {
  questions: ClarificationQuestion[];
  onSubmit: (answers: string[]) => void;
}

export function ClarificationWizard({ questions, onSubmit }: ClarificationWizardProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<string[]>(() => Array(questions.length).fill(""));
  const [selectedOption, setSelectedOption] = useState<"guess_1" | "guess_2" | "custom" | null>(null);
  const [customText, setCustomText] = useState("");
  const [animateKey, setAnimateKey] = useState(0);

  const currentQuestion = questions[currentIndex];

  // Load answer when index changes
  useEffect(() => {
    if (!currentQuestion) return;
    const currentAnswer = answers[currentIndex];
    if (currentAnswer === currentQuestion.guess_1 && currentQuestion.guess_1) {
      setSelectedOption("guess_1");
      setCustomText("");
    } else if (currentAnswer === currentQuestion.guess_2 && currentQuestion.guess_2) {
      setSelectedOption("guess_2");
      setCustomText("");
    } else if (currentAnswer) {
      setSelectedOption("custom");
      setCustomText(currentAnswer);
    } else {
      setSelectedOption(null);
      setCustomText("");
    }
    setAnimateKey((prev) => prev + 1);
  }, [currentIndex, questions, answers, currentQuestion]);

  if (!currentQuestion) {
    return null;
  }

  const handleSelectOption = (option: "guess_1" | "guess_2") => {
    setSelectedOption(option);
    const value = option === "guess_1" ? currentQuestion.guess_1 : currentQuestion.guess_2;
    const newAnswers = [...answers];
    newAnswers[currentIndex] = value;
    setAnswers(newAnswers);
  };

  const handleCustomTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setCustomText(value);
    setSelectedOption(value ? "custom" : null);
    const newAnswers = [...answers];
    newAnswers[currentIndex] = value;
    setAnswers(newAnswers);
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handleBack = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const isCurrentAnswered = Boolean(answers[currentIndex]?.trim());

  return (
    <div className="clarification-wizard-card">
      <div className="clarification-wizard-progress">
        <div
          className="clarification-wizard-progress-bar"
          style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
        />
      </div>

      <div className="clarification-wizard-header">
        <span className="clarification-wizard-step-indicator">
          Question {currentIndex + 1} of {questions.length}
        </span>
        <h4 className="clarification-wizard-title">Please Clarify Your Request</h4>
      </div>

      <div key={animateKey} className="clarification-wizard-body question-slide-active">
        <p className="clarification-wizard-question">{currentQuestion.question}</p>

        <div className="clarification-wizard-options">
          {currentQuestion.guess_1 && (
            <button
              type="button"
              className={`clarification-wizard-option-box ${selectedOption === "guess_1" ? "active" : ""}`}
              onClick={() => handleSelectOption("guess_1")}
            >
              <div className="option-checkbox">
                {selectedOption === "guess_1" && <div className="option-checkbox-inner" />}
              </div>
              <div className="option-text-container">
                <span className="option-label">Option A</span>
                <span className="option-value">{currentQuestion.guess_1}</span>
              </div>
            </button>
          )}

          {currentQuestion.guess_2 && (
            <button
              type="button"
              className={`clarification-wizard-option-box ${selectedOption === "guess_2" ? "active" : ""}`}
              onClick={() => handleSelectOption("guess_2")}
            >
              <div className="option-checkbox">
                {selectedOption === "guess_2" && <div className="option-checkbox-inner" />}
              </div>
              <div className="option-text-container">
                <span className="option-label">Option B</span>
                <span className="option-value">{currentQuestion.guess_2}</span>
              </div>
            </button>
          )}

          <div className={`clarification-wizard-option-box custom-option-box ${selectedOption === "custom" ? "active" : ""}`}>
            <div className="option-checkbox">
              {selectedOption === "custom" && <div className="option-checkbox-inner" />}
            </div>
            <div className="option-text-container">
              <span className="option-label">Custom Opinion</span>
              <input
                type="text"
                className="custom-opinion-input"
                placeholder="Or write custom opinion here..."
                value={customText}
                onChange={handleCustomTextChange}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="clarification-wizard-footer">
        {currentIndex > 0 ? (
          <button type="button" className="wizard-back-button" onClick={handleBack}>
            Back
          </button>
        ) : (
          <div />
        )}

        {currentIndex === questions.length - 1 ? (
          <button
            type="button"
            className="wizard-submit-button"
            disabled={!isCurrentAnswered}
            onClick={() => onSubmit(answers)}
          >
            Submit Answers
          </button>
        ) : (
          <button
            type="button"
            className="wizard-next-button"
            disabled={!isCurrentAnswered}
            onClick={handleNext}
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}
