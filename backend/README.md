# Backend (Spring Boot 3, Java 21)

Chưa khởi tạo mã nguồn. Kiến trúc đã chốt ở [docs/03-thiet-ke.md](../docs/03-thiet-ke.md), mục 1.2 và mục 4.

- Package gốc: `com.team.health`
- Các module: `shared`, `identity`, `profile`, `knowledge`, `screening`, `cabinet`, `monitoring`, `caregiver`, `notification`, `admin`
- Mỗi module có 4 tầng: `api` / `application` / `domain` / `infrastructure`
- Migration Flyway: [`src/main/resources/db/migration/`](src/main/resources/db/migration/)
