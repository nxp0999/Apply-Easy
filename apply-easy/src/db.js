import sqlite3 from 'sqlite3';
import { open } from 'sqlite3';

const db = open({
  filename: './output/applications.db',
  driver: sqlite3.Database,
});

export default db;