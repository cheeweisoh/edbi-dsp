# EDBI Data Sharing Platform

## Overview

The **EDBI Data Sharing Platform** (edbi-dsp) is an Enterprise Data & Business Intelligence platform that enables government agencies to securely share datasets internally, manage granular access permissions, and query data using natural language through a Text-to-SQL interface.

### Key Features

- **Dataset Management**: Upload, register, and organize datasets with rich metadata
- **Access Control**: Fine-grained permission system supporting user and group-based access
- **Text-to-SQL Query Interface**: Query datasets using natural language powered by Mistral Large 3
- **Unity Catalog Integration**: Connect to Databricks Unity Catalog for centralized data governance
- **Audit Trail**: Complete query logging for compliance and monitoring
- **Role-Based Access**: Support for regular users, dataset owners, and superusers

### Technology Stack

- **Backend**: FastAPI (Python 3.14), SQLAlchemy (async), Pydantic v2
- **Frontend**: Streamlit
- **Database**: SQLite (development) with async support via aiosqlite
- **LLM**: Mistral Large 3 via Ollama for Text-to-SQL generation
- **Data Integration**: Databricks Unity Catalog, Databricks SQL Warehouse

---

## Quick Start

### Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) package manager
- [Ollama](https://ollama.ai/) for local LLM inference
- Databricks workspace credentials (for Unity Catalog integration)

### Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/cheeweisoh/edbi-dsp
   cd edbi-dsp
   ```

2. **Configure environment variables**:
   
   Edit `backend/.env` to set your Databricks credentials and bootstrap users:
   ```bash
   # Database
   DATABASE_URL=sqlite+aiosqlite:///./edbi_dsp.db
   
   # Security
   SECRET_KEY=super-secret-replace-in-prod
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   
   # Bootstrap Users
   BOOTSTRAP_USER_EMAIL=admin
   BOOTSTRAP_USER_PASSWORD=changeme
   BOOTSTRAP_USER2_EMAIL=user
   BOOTSTRAP_USER2_PASSWORD=changeme2
   
   # Databricks Unity Catalog
   DATABRICKS_HOST=https://your-workspace.cloud.databricks.com/
   DATABRICKS_TOKEN=your-databricks-token
   DATABRICKS_SQL_WAREHOUSE_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
   DATABRICKS_UC_CATALOG=your-catalog-name
   DATABRICKS_UC_SCHEMA=your-schema-name
   ```

3. **Install dependencies, initialize database, and start all services**:
   ```bash
   make all
   ```

   This command will:
   - Reset the database
   - Create tables, bootstrap data from Unity Catalog, and bootstrap users from local file
   - Start the Ollama service
   - Pull the `mistral-large-3:675b-cloud` model
   - Start the backend API (uvicorn) on port 8000
   - Start the frontend (Streamlit) on port 8501

4. **Access the platform**:
   - **Frontend Interface**: http://localhost:8501
   - **Backend API Documentation**: http://localhost:8000/docs (Swagger UI)
   - **Alternative API Docs**: http://localhost:8000/redoc (ReDoc)

### Stopping the Platform

To stop all running services (backend, frontend, and Ollama):

```bash
make stop
```

---

## Bootstrapped Users & Access

The platform comes pre-configured with two users for testing and demonstration:

### 1. **Admin User** (Superuser)
- **Email**: `admin`
- **Password**: `changeme`
- **Role**: System Administrator (superuser)

**Capabilities**:
- Full platform access (bypass all permission checks)
- Create, read, update, and delete any dataset
- Manage all users and groups
- Grant/revoke permissions on any dataset
- Query any dataset regardless of permissions
- View all query logs across the system
- Bootstrap and manage Unity Catalog dataset imports

**Use Cases**:
- Platform administration and configuration
- Initial dataset onboarding from Unity Catalog
- Granting access to new users and teams
- System monitoring and audit reviews

---

### 2. **Regular User**
- **Email**: `user`
- **Password**: `changeme2`
- **Role**: Regular user (non-superuser)
- **Group Membership**: `team-leaders` (automatically added during bootstrap)

**Capabilities**:
- View datasets they own or have been granted `view` permission on
- Query datasets they have `query` permission on (direct or via group membership)
- Edit dataset metadata for datasets they own or have `edit` permission on
- Manage permissions for datasets they own
- View their own query history
- Create new datasets (becomes owner with full control)

**Limitations**:
- Cannot access datasets without explicit permission
- Cannot view or modify other users' data unless granted access
- Cannot grant permissions on datasets they don't own
- Cannot perform administrative functions

---

### Group: `team-leaders`
- **Description**: Officers that can only view officer case load datasets
- **Members**: `user` (Regular User)
- **Created By**: `admin`

This group is used to demonstrate group-based permission management. Permissions granted to this group apply to all members.

---

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login with email/password, receive JWT token
- `POST /api/v1/auth/register` - Register a new user account

### Users
- `GET /api/v1/users/me` - Get current user profile
- `PUT /api/v1/users/me` - Update current user profile

### Datasets
- `GET /api/v1/datasets` - List all accessible datasets
- `POST /api/v1/datasets` - Create a new dataset
- `GET /api/v1/datasets/{dataset_id}` - Get dataset details
- `PUT /api/v1/datasets/{dataset_id}` - Update dataset metadata
- `DELETE /api/v1/datasets/{dataset_id}` - Delete a dataset

### Permissions
- `GET /api/v1/datasets/{dataset_id}/permissions` - List permissions for a dataset
- `POST /api/v1/datasets/{dataset_id}/permissions` - Grant permission
- `DELETE /api/v1/datasets/{dataset_id}/permissions/{permission_id}` - Revoke permission

### Query (Text-to-SQL)
- `POST /api/v1/query/execute` - Execute a natural language query
- `GET /api/v1/query/history` - Get query history
