export interface Todo {
  id: number;
  title: string;
  done: boolean;
  createdAt: string; // ISO 8601
  due: string | null; // YYYY-MM-DD
  link: string | null; // a URL the user attached
}
