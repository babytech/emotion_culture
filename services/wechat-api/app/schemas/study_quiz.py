from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class QuizQuestionType(str, Enum):
    RADIO = "radio"
    CHECK = "check"
    FILL = "fill"


class QuizQuestionOption(BaseModel):
    item: str
    content: str


class QuizFillItem(BaseModel):
    item: str
    content: str


class QuizPaperQuestion(BaseModel):
    question_id: str
    type: QuizQuestionType
    stem: str
    options: list[QuizQuestionOption] = Field(default_factory=list)
    fills: list[QuizFillItem] = Field(default_factory=list)
    audio: str = "no"
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "normal"


class QuizPaperResponse(BaseModel):
    paper_id: str
    course: str
    title: str
    version: str
    total_questions: int
    questions: list[QuizPaperQuestion] = Field(default_factory=list)


class QuizAnswerSubmission(BaseModel):
    question_id: str
    answer: Any = None


class QuizSubmitRequest(BaseModel):
    course: str = "english"
    paper_id: Optional[str] = None
    submit_token: Optional[str] = None
    answers: list[QuizAnswerSubmission] = Field(default_factory=list)


class QuizQuestionResult(BaseModel):
    question_id: str
    question_type: QuizQuestionType
    stem: str
    correct: bool
    partial: bool = False
    score: float = 0.0
    score_full: float = 0.0
    user_answer: str = ""
    right_answer: str = ""


class QuizWrongItem(BaseModel):
    wrong_id: str
    question_id: str
    question_type: QuizQuestionType
    stem: str
    user_answer: str
    right_answer: str
    score: float
    score_full: float


class QuizRecordSummary(BaseModel):
    quiz_record_id: str
    course: str
    submitted_at: str
    total_questions: int
    answered_questions: int
    score: int
    grade: str
    correct_count: int
    partial_count: int
    wrong_count: int


class QuizPointsReward(BaseModel):
    awarded: bool = False
    points: int = 0
    balance: Optional[int] = None
    reason: str = "quiz_submit"
    action_key: Optional[str] = None


class QuizSubmitResponse(BaseModel):
    quiz_record: QuizRecordSummary
    results: list[QuizQuestionResult] = Field(default_factory=list)
    wrong_items: list[QuizWrongItem] = Field(default_factory=list)
    next_action_hint: str
    points_reward: Optional[QuizPointsReward] = None


class QuizHistoryResponse(BaseModel):
    items: list[QuizRecordSummary] = Field(default_factory=list)
    total: int = 0


class QuizWrongbookEntry(BaseModel):
    wrongbook_id: str
    question_id: str
    question_type: QuizQuestionType
    stem: str
    right_answer: str
    latest_user_answer: str
    wrong_times: int
    last_wrong_at: str
    first_wrong_at: str


class QuizWrongbookResponse(BaseModel):
    items: list[QuizWrongbookEntry] = Field(default_factory=list)
    total: int = 0


class QuizBankIngestQuestion(BaseModel):
    question_id: str
    type: QuizQuestionType
    stem: str
    options: list[QuizQuestionOption] = Field(default_factory=list)
    fills: list[QuizFillItem] = Field(default_factory=list)
    answer: str
    audio: str = "no"
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "normal"


class QuizBankIngestResponse(BaseModel):
    course: str
    title: str
    version: str
    source_type: str
    persisted: bool = True
    total_questions: int
    questions: list[QuizBankIngestQuestion] = Field(default_factory=list)
    excel_rows: list[list[str]] = Field(default_factory=list)
    note: Optional[str] = None
