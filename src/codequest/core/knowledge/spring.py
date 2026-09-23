"""Conceptos de Spring Boot, Spring Data y JPA.

Cada `summary` es la respuesta correcta de una pregunta de alternativas y cada
`distractor` una afirmación falsa pero verosímil. Mantener ambos con un estilo y una
longitud parecidos: si la correcta es siempre la más larga, se adivina sin saber.
"""

from codequest.core.knowledge.models import Concept, Topic

T = Topic

CONCEPTS: tuple[Concept, ...] = (
    # --- Spring Web -------------------------------------------------------------------
    Concept(
        id="spring.rest-controller",
        title="@RestController",
        topic=T.WEB,
        summary="Marca la clase como controlador web que devuelve datos (normalmente JSON) en la respuesta.",
        explanation="@RestController combina @Controller y @ResponseBody. Al arrancar, Spring detecta la "
                    "clase, crea una instancia y le envía las peticiones HTTP que coinciden con sus rutas.\n\n"
                    "Lo que devuelve cada método (un objeto, una lista, un ResponseEntity) se convierte "
                    "automáticamente en el cuerpo de la respuesta, normalmente JSON. Por eso no necesitas "
                    "plantillas HTML: es la base de una API REST.",
        analogy="Es como el mostrador de una tienda: recibe los pedidos de los clientes (peticiones HTTP) y "
                "les entrega directamente el producto empaquetado (JSON), sin pasar por el escaparate.",
        distractors=(
            "Convierte la clase en una tabla de la base de datos y cada método en una consulta.",
            "Hace que todos los métodos de la clase se ejecuten dentro de una misma transacción.",
            "Registra la clase como repositorio para que Spring genere sus consultas automáticamente.",
        ),
        youtube_query="Spring Boot @RestController explicado",
    ),
    Concept(
        id="spring.controller",
        title="@Controller",
        topic=T.WEB,
        summary="Marca la clase como controlador web que por defecto devuelve una vista HTML, no datos.",
        explanation="Un @Controller clásico trabaja con vistas: el método devuelve un nombre como \"home\" y "
                    "Spring busca la plantilla correspondiente (Thymeleaf, JSP…) para generar el HTML.\n\n"
                    "Si quieres devolver JSON desde un @Controller tienes que añadir @ResponseBody al método; "
                    "@RestController hace eso por ti en toda la clase.",
        analogy="Es un camarero que, en vez de darte la comida en una bolsa, te lleva a la mesa ya servida "
                "(la página HTML completa).",
        distractors=(
            "Convierte automáticamente cualquier objeto devuelto en JSON sin configuración adicional.",
            "Define la conexión con la base de datos que usarán los servicios de la aplicación.",
            "Marca la clase como punto de entrada principal que arranca la aplicación Spring Boot.",
        ),
        youtube_query="Spring @Controller vs @RestController",
    ),
    Concept(
        id="spring.request-mapping",
        title="@RequestMapping",
        topic=T.WEB,
        summary="Define la ruta que atiende la clase o el método; en la clase, es el prefijo común.",
        explanation="Colocado sobre la clase, @RequestMapping(\"/api/users\") hace que todas las rutas de sus "
                    "métodos empiecen por /api/users. Así un @GetMapping(\"/{id}\") dentro de la clase "
                    "responde en /api/users/{id}.\n\n"
                    "También puede ir sobre un método y fijar el verbo con method = RequestMethod.GET, aunque "
                    "hoy se prefieren las versiones cortas como @GetMapping o @PostMapping.",
        analogy="Es como el nombre de una calle: cada método es un número de portal dentro de esa calle.",
        distractors=(
            "Mapea la clase a una tabla de la base de datos con el nombre indicado.",
            "Indica la carpeta del proyecto donde Spring debe buscar los archivos de configuración.",
            "Registra un filtro de seguridad que se ejecuta antes de cada petición a la aplicación.",
        ),
        youtube_query="Spring @RequestMapping rutas",
    ),
    Concept(
        id="spring.get-mapping",
        title="@GetMapping",
        topic=T.WEB,
        summary="Asocia el método a las peticiones HTTP GET de esa ruta, para consultar datos.",
        explanation="Cuando llega un GET a la ruta indicada, Spring ejecuta ese método y devuelve su resultado. "
                    "GET es el verbo de lectura: pedir la lista de usuarios, un usuario por id, etc.\n\n"
                    "Por convención un GET no debe cambiar datos: se puede repetir sin efectos secundarios, "
                    "y los navegadores o proxies pueden cachearlo.",
        analogy="Es como mirar un escaparate: puedes hacerlo cuantas veces quieras sin cambiar nada de la tienda.",
        distractors=(
            "Asocia el método a las peticiones HTTP POST para crear un recurso nuevo.",
            "Hace que el método obtenga automáticamente el valor de un campo de configuración.",
            "Marca el método como getter de la entidad para que JPA lea la columna correspondiente.",
        ),
        youtube_query="Spring Boot @GetMapping ejemplo",
    ),
    Concept(
        id="spring.post-mapping",
        title="@PostMapping",
        topic=T.WEB,
        summary="Asocia el método a las peticiones HTTP POST de esa ruta, para crear un recurso.",
        explanation="POST es el verbo para enviar datos que crean algo nuevo: registrar un usuario, crear un "
                    "pedido… Los datos suelen llegar en el cuerpo de la petición y se reciben con "
                    "@RequestBody.\n\n"
                    "A diferencia de GET, repetir un POST normalmente crea otro recurso más, por eso los "
                    "navegadores avisan antes de reenviar un formulario.",
        analogy="Es como entregar un formulario en una ventanilla: cada vez que lo entregas se abre un trámite nuevo.",
        distractors=(
            "Asocia el método a las peticiones HTTP GET para listar los recursos existentes.",
            "Hace que el método se ejecute después de que Spring termine de crear todos los beans.",
            "Publica automáticamente el resultado del método en una cola de mensajes.",
        ),
        youtube_query="Spring Boot @PostMapping @RequestBody",
    ),
    Concept(
        id="spring.put-mapping",
        title="@PutMapping",
        topic=T.WEB,
        summary="Asocia el método a peticiones HTTP PUT, para reemplazar un recurso existente.",
        explanation="PUT envía la versión completa y actualizada de un recurso, por ejemplo todos los datos "
                    "de un usuario. Suele combinarse con @PathVariable para indicar cuál (/users/{id}) y con "
                    "@RequestBody para los datos nuevos.\n\n"
                    "PUT es idempotente: enviar la misma actualización dos veces deja el recurso igual que "
                    "enviarla una.",
        analogy="Es como sustituir una ficha entera en un archivador por una ficha nueva ya rellenada.",
        distractors=(
            "Asocia el método a peticiones que eliminan el recurso indicado en la URL.",
            "Guarda el resultado del método en caché para no volver a calcularlo.",
            "Indica que el método añade un campo nuevo a la tabla de la entidad.",
        ),
        youtube_query="HTTP PUT vs PATCH Spring Boot",
    ),
    Concept(
        id="spring.patch-mapping",
        title="@PatchMapping",
        topic=T.WEB,
        summary="Asocia el método a peticiones HTTP PATCH, para modificar parte de un recurso.",
        explanation="PATCH envía únicamente los campos que cambian (por ejemplo, solo el email), en lugar del "
                    "recurso completo como hace PUT.\n\n"
                    "Es útil cuando los objetos son grandes o cuando distintos clientes modifican partes "
                    "diferentes del mismo recurso.",
        analogy="Es como corregir una sola línea de una ficha con típex en lugar de rehacer la ficha entera.",
        distractors=(
            "Asocia el método a peticiones que crean un recurso nuevo desde cero.",
            "Aplica automáticamente las migraciones pendientes de la base de datos.",
            "Marca el método como una versión provisional que Spring ignora en producción.",
        ),
        youtube_query="Spring Boot @PatchMapping actualización parcial",
    ),
    Concept(
        id="spring.delete-mapping",
        title="@DeleteMapping",
        topic=T.WEB,
        summary="Asocia el método a peticiones HTTP DELETE de esa ruta, para eliminar un recurso.",
        explanation="DELETE indica que el cliente quiere borrar el recurso de la URL, por ejemplo "
                    "DELETE /users/42. El id suele llegar con @PathVariable.\n\n"
                    "Es habitual responder 204 No Content cuando el borrado sale bien y 404 si el recurso no "
                    "existía.",
        analogy="Es como pedir en recepción que den de baja tu tarjeta de socio: indicas cuál y la anulan.",
        distractors=(
            "Borra automáticamente los datos temporales de la sesión al terminar la petición.",
            "Elimina el método del contexto de Spring cuando la aplicación se apaga.",
            "Asocia el método a peticiones que devuelven la lista de recursos eliminados.",
        ),
        youtube_query="Spring Boot @DeleteMapping REST",
    ),
    Concept(
        id="spring.path-variable",
        title="@PathVariable",
        topic=T.WEB,
        summary="Toma un valor de la propia URL (como el 42 de /users/42) y lo pasa al método.",
        explanation="Si la ruta es /users/{id}, el trozo {id} es una variable de ruta. Con @PathVariable Long id "
                    "Spring extrae ese valor de la URL y lo convierte al tipo del parámetro.\n\n"
                    "Si el nombre del parámetro no coincide con el de la ruta, se indica explícitamente: "
                    "@PathVariable(\"id\") Long userId.",
        analogy="Es como leer el número de habitación escrito en la puerta: la dirección misma te dice a quién buscas.",
        distractors=(
            "Lee el cuerpo JSON de la petición y lo convierte en un objeto Java.",
            "Obtiene un parámetro de la query string, como ?page=2, y lo pasa al método.",
            "Declara una variable de entorno que el método puede modificar durante la ejecución.",
        ),
        youtube_query="Spring @PathVariable vs @RequestParam",
    ),
    Concept(
        id="spring.request-body",
        title="@RequestBody",
        topic=T.WEB,
        summary="Convierte el cuerpo de la petición (normalmente JSON) en un objeto Java.",
        explanation="Cuando un cliente envía un POST o PUT con JSON, @RequestBody hace que Spring lea ese JSON y "
                    "construya el objeto indicado (por ejemplo, un UserDTO) usando Jackson.\n\n"
                    "Suele combinarse con @Valid para comprobar las reglas de validación del objeto antes de "
                    "entrar al método.",
        analogy="Es como un traductor que recibe una carta en otro idioma (JSON) y te la entrega ya en el tuyo (un objeto Java).",
        distractors=(
            "Toma un valor de la URL, como el id de /users/42, y lo pasa al método.",
            "Devuelve el objeto del método como cuerpo HTML de la respuesta.",
            "Guarda el objeto recibido directamente en la base de datos sin pasar por el servicio.",
        ),
        youtube_query="Spring Boot @RequestBody JSON",
    ),
    Concept(
        id="spring.request-param",
        title="@RequestParam",
        topic=T.WEB,
        summary="Lee un parámetro de la query string de la URL (como ?page=2) y lo pasa al método.",
        explanation="En /products?page=2&size=20, page y size son parámetros de consulta. Con "
                    "@RequestParam int page Spring los extrae y convierte al tipo del parámetro.\n\n"
                    "Con required = false o defaultValue = \"0\" el parámetro se vuelve opcional.",
        analogy="Son como las opciones que marcas al pedir un café: tamaño y leche no cambian qué pides, solo cómo.",
        distractors=(
            "Toma un valor que forma parte de la ruta, como el 42 de /users/42.",
            "Convierte el cuerpo JSON de la petición en un objeto Java.",
            "Obliga a que el método reciba siempre una petición autenticada con un token válido.",
        ),
        youtube_query="Spring @RequestParam query params",
    ),
    # --- Inyección de dependencias y componentes ---------------------------------------
    Concept(
        id="spring.service",
        title="@Service",
        topic=T.DI,
        summary="Marca la clase como componente de lógica de negocio que Spring crea e inyecta.",
        explanation="@Service es una especialización de @Component: Spring la detecta al arrancar, crea un único "
                    "objeto (un bean) y lo inyecta en los controladores u otros servicios que lo pidan.\n\n"
                    "Técnicamente funciona igual que @Component, pero comunica la intención: aquí viven las "
                    "reglas de negocio, entre el controlador (web) y el repositorio (datos).",
        analogy="Es la cocina de un restaurante: el camarero (controlador) toma el pedido, pero donde se prepara el plato es aquí.",
        distractors=(
            "Expone la clase como servicio web accesible directamente desde el navegador.",
            "Hace que la clase se ejecute en un hilo separado cada vez que se llama.",
            "Convierte la clase en una entidad que Spring guarda en la base de datos.",
        ),
        youtube_query="Spring Boot @Service capa de servicio",
    ),
    Concept(
        id="spring.repository-annotation",
        title="@Repository",
        topic=T.DATA,
        summary="Marca la clase de acceso a datos y traduce los errores de BD a excepciones de Spring.",
        explanation="@Repository es otra especialización de @Component pensada para la capa de persistencia. "
                    "Además de registrar el bean, activa la traducción de excepciones: un error específico de "
                    "MySQL se convierte en una DataAccessException de Spring.\n\n"
                    "En las interfaces que extienden JpaRepository no hace falta ponerla: Spring Data ya las "
                    "detecta y registra.",
        analogy="Es el archivero de la empresa: el único que sabe dónde está guardado cada documento.",
        distractors=(
            "Crea automáticamente la tabla de la base de datos a partir de los campos de la clase.",
            "Guarda en caché los resultados de todos los métodos de la clase.",
            "Expone los métodos de la clase como endpoints REST de consulta.",
        ),
        youtube_query="Spring @Repository explicado",
    ),
    Concept(
        id="spring.component",
        title="@Component",
        topic=T.DI,
        summary="Registra la clase como bean genérico para que Spring la cree y pueda inyectarla.",
        explanation="Es la anotación base del escaneo de componentes. @Service, @Repository y @Controller son "
                    "variantes de @Component con un significado más específico.\n\n"
                    "Se usa para clases de apoyo que no encajan en esas capas: helpers, listeners, "
                    "validadores personalizados…",
        analogy="Es como darte de alta en el registro del edificio: a partir de ahí, cualquiera que te necesite sabe dónde encontrarte.",
        distractors=(
            "Convierte la clase en un componente visual que se muestra en la interfaz web.",
            "Divide la clase en varios módulos que se cargan de forma independiente.",
            "Marca la clase como abstracta para que no se pueda instanciar.",
        ),
        youtube_query="Spring @Component escaneo de componentes",
    ),
    Concept(
        id="spring.autowired",
        title="@Autowired",
        topic=T.DI,
        summary="Pide a Spring que inyecte automáticamente otro bean en ese campo o constructor.",
        explanation="En lugar de hacer new UserRepository(), declaras que lo necesitas y Spring te entrega la "
                    "instancia que gestiona. Eso es inyección de dependencias.\n\n"
                    "Hoy se recomienda la inyección por constructor (un constructor con las dependencias como "
                    "parámetros, sin @Autowired), porque permite campos final y facilita los tests.",
        analogy="Es como pedir en recepción una herramienta: no la fabricas tú, alguien te la trae ya lista.",
        distractors=(
            "Genera automáticamente los getters y setters del campo anotado.",
            "Hace que el campo se guarde automáticamente en la base de datos al cambiar.",
            "Crea una copia nueva del objeto cada vez que se accede al campo.",
        ),
        youtube_query="Spring @Autowired vs inyección por constructor",
    ),
    Concept(
        id="spring.configuration",
        title="@Configuration",
        topic=T.CONFIG,
        summary="Marca la clase como fuente de configuración cuyos métodos @Bean definen beans.",
        explanation="Una clase @Configuration es el lugar donde declaras, con código Java, beans que no puedes "
                    "anotar directamente, por ejemplo un PasswordEncoder o un cliente HTTP de una librería "
                    "externa.\n\n"
                    "Spring la procesa al arrancar y registra lo que devuelven sus métodos @Bean.",
        analogy="Es el manual de montaje del contenedor: indica qué piezas especiales hay que fabricar y cómo.",
        distractors=(
            "Lee el archivo application.properties y lo convierte en una tabla de la base de datos.",
            "Marca la clase como controlador de las pantallas de ajustes de la aplicación.",
            "Impide que se modifique la clase una vez que la aplicación ha arrancado.",
        ),
        youtube_query="Spring @Configuration @Bean",
    ),
    Concept(
        id="spring.bean",
        title="@Bean",
        topic=T.CONFIG,
        summary="Registra como bean de Spring el objeto que devuelve el método, para poder inyectarlo.",
        explanation="Se usa dentro de clases @Configuration. Spring llama al método una vez, guarda el objeto "
                    "devuelto y lo inyecta en quien lo necesite.\n\n"
                    "Es la forma de convertir en bean una clase que no es tuya (de una librería) y que por "
                    "tanto no puedes anotar con @Component.",
        analogy="Es como encargar una pieza a medida: el método explica cómo fabricarla y Spring la guarda en el almacén.",
        distractors=(
            "Convierte el método en un endpoint HTTP que devuelve la configuración actual de la app.",
            "Hace que el método se ejecute cada vez que se inyecta la dependencia.",
            "Marca el método como obsoleto para que Spring lo ignore al arrancar.",
        ),
        youtube_query="Spring @Bean explicado",
    ),
    Concept(
        id="spring.value",
        title="@Value",
        topic=T.CONFIG,
        summary="Inyecta un valor de configuración, como una propiedad de application.properties.",
        explanation="Con @Value(\"${app.jwt.secret}\") Spring busca la propiedad app.jwt.secret en la "
                    "configuración (application.properties, variables de entorno…) y la asigna al campo.\n\n"
                    "Así los valores que cambian entre entornos no quedan escritos en el código.",
        analogy="Es como un formulario con huecos: el código deja el hueco y la configuración lo rellena.",
        distractors=(
            "Marca el campo como obligatorio para que no pueda guardarse vacío en la base de datos.",
            "Convierte el campo en una constante que no puede cambiar después de compilar.",
            "Valida que el valor del campo tenga el formato indicado entre paréntesis.",
        ),
        youtube_query="Spring Boot @Value application.properties",
    ),
    Concept(
        id="spring.boot-application",
        title="@SpringBootApplication",
        topic=T.CONFIG,
        summary="Marca la clase principal y activa la autoconfiguración y el escaneo de componentes.",
        explanation="Combina @Configuration, @EnableAutoConfiguration y @ComponentScan. Por eso Spring encuentra "
                    "tus controladores y servicios: busca en el paquete de esta clase y en sus subpaquetes.\n\n"
                    "La autoconfiguración revisa tus dependencias (por ejemplo, el driver de MySQL) y "
                    "configura lo necesario sin que escribas nada.",
        analogy="Es el interruptor general de la casa: al encenderlo se activan todas las instalaciones.",
        distractors=(
            "Convierte la clase en el único controlador REST de la aplicación.",
            "Define la versión de Java con la que debe compilarse el proyecto.",
            "Crea automáticamente la base de datos y todas sus tablas al compilar el proyecto.",
        ),
        youtube_query="@SpringBootApplication qué hace",
    ),
    # --- Transacciones ------------------------------------------------------------------
    Concept(
        id="spring.transactional",
        title="@Transactional",
        topic=T.TRANSACTIONS,
        summary="Hace que las operaciones de base de datos se ejecuten dentro de una transacción.",
        explanation="@Transactional le indica a Spring que todo lo que el método hace en la base de datos forma "
                    "parte de una sola transacción.\n\n"
                    "Imagina que tienes que hacer tres cambios: descontar dinero, registrar el movimiento y "
                    "depositar el dinero. Si el tercero falla, no quieres que los dos primeros queden "
                    "guardados. Con @Transactional, ante una excepción Spring revierte (rollback) la "
                    "operación completa.\n\n"
                    "Con readOnly = true se avisa de que solo se leerá, lo que permite algunas optimizaciones.",
        analogy="Es como guardar la partida solo cuando todas las acciones de la misión se completaron: si "
                "mueres a mitad, vuelves al último punto guardado.",
        distractors=(
            "Convierte el método en un endpoint HTTP que se puede llamar desde el navegador.",
            "Hace que el resultado del método se convierta automáticamente en JSON.",
            "Inyecta automáticamente el repositorio que usa el método.",
        ),
        youtube_query="Spring @Transactional explicado rollback",
    ),
    # --- JPA ----------------------------------------------------------------------------
    Concept(
        id="jpa.entity",
        title="@Entity",
        topic=T.JPA,
        summary="Indica que la clase se guarda en la base de datos: una tabla, y cada objeto una fila.",
        explanation="Una entidad es una clase Java que representa una tabla. JPA (normalmente con Hibernate) "
                    "traduce sus campos a columnas y se encarga de los INSERT, UPDATE y SELECT.\n\n"
                    "Toda entidad necesita un campo @Id que la identifique y un constructor sin argumentos.",
        analogy="Es el molde de una ficha de archivo: la clase define los apartados y cada ficha rellenada es una fila.",
        distractors=(
            "Marca la clase como objeto de transferencia que solo viaja entre el cliente y el servidor.",
            "Registra la clase como servicio para inyectarla en los controladores.",
            "Hace que la clase no pueda modificarse una vez creada.",
        ),
        youtube_query="JPA @Entity Spring Boot",
    ),
    Concept(
        id="jpa.table",
        title="@Table",
        topic=T.JPA,
        summary="Personaliza la tabla a la que se asocia la entidad: su nombre, índices o restricciones.",
        explanation="Sin @Table, JPA usa el nombre de la clase como nombre de tabla. Con @Table(name = \"users\") "
                    "eliges otro, útil si la tabla ya existe o si el nombre es palabra reservada (como order).\n\n"
                    "También permite declarar restricciones, por ejemplo que el email sea único.",
        analogy="Es la etiqueta del cajón del archivador: el contenido es el mismo, pero decides qué nombre lleva fuera.",
        distractors=(
            "Hace que la entidad se muestre como una tabla HTML en las respuestas de la API REST.",
            "Crea una tabla temporal en memoria que se borra al terminar la petición.",
            "Indica cuántas filas como máximo puede guardar la entidad.",
        ),
        youtube_query="JPA @Table name uniqueConstraints",
    ),
    Concept(
        id="jpa.id",
        title="@Id",
        topic=T.JPA,
        summary="Marca el campo como clave primaria, el valor que identifica cada fila.",
        explanation="JPA necesita saber qué campo distingue a cada registro para poder buscarlo, actualizarlo o "
                    "borrarlo. Ese campo es el @Id.\n\n"
                    "Casi siempre va junto a @GeneratedValue para que el valor lo genere la base de datos.",
        analogy="Es el número de DNI de cada fila: puede haber dos personas con el mismo nombre, pero no con el mismo DNI.",
        distractors=(
            "Hace que el campo se oculte en las respuestas JSON de la API.",
            "Indica que el campo se usa para ordenar los resultados de las consultas.",
            "Convierte el campo en una referencia a otra entidad relacionada.",
        ),
        youtube_query="JPA @Id @GeneratedValue",
    ),
    Concept(
        id="jpa.generated-value",
        title="@GeneratedValue",
        topic=T.JPA,
        summary="Indica que el valor de la clave primaria se genera automáticamente al insertar.",
        explanation="Con strategy = GenerationType.IDENTITY el id lo asigna la base de datos (AUTO_INCREMENT en "
                    "MySQL) al insertar la fila. Por eso, al crear un objeto nuevo, su id es null hasta que se "
                    "guarda.\n\n"
                    "Otras estrategias, como SEQUENCE, usan secuencias de la base de datos.",
        analogy="Es como el número de turno de la carnicería: no lo eliges tú, te lo da la máquina al llegar.",
        distractors=(
            "Genera automáticamente los getters y setters de todos los campos de la entidad.",
            "Rellena el campo con datos de ejemplo cuando la tabla está vacía.",
            "Genera un valor aleatorio nuevo cada vez que se lee el campo.",
        ),
        youtube_query="JPA GenerationType IDENTITY vs SEQUENCE",
    ),
    Concept(
        id="jpa.column",
        title="@Column",
        topic=T.JPA,
        summary="Personaliza la columna del campo: su nombre, longitud o si admite nulos.",
        explanation="Sin @Column, JPA crea una columna con el nombre del campo y valores por defecto. Con "
                    "@Column(nullable = false, length = 120) defines reglas concretas.\n\n"
                    "Estas reglas afectan al esquema de la tabla; para validar los datos antes de guardarlos "
                    "se usan además anotaciones como @NotBlank.",
        analogy="Es como configurar una casilla de un formulario: cuánto texto cabe y si es obligatoria.",
        distractors=(
            "Hace que el campo se muestre como una columna en las tablas de la interfaz web.",
            "Ordena los resultados de las consultas por el valor de ese campo.",
            "Divide el valor del campo en varias columnas de la base de datos.",
        ),
        youtube_query="JPA @Column nullable length",
    ),
    Concept(
        id="jpa.one-to-many",
        title="@OneToMany",
        topic=T.JPA,
        summary="Relaciona una instancia con muchas de otra entidad, como un usuario con sus pedidos.",
        explanation="El campo suele ser una colección (List<Order>). Con mappedBy = \"user\" indicas que la "
                    "clave foránea vive en la otra entidad (el campo user de Order, con @ManyToOne).\n\n"
                    "cascade = CascadeType.ALL propaga operaciones: al guardar o borrar el usuario también se "
                    "guardan o borran sus pedidos.",
        analogy="Es como un profesor con su lista de alumnos: un profesor, muchos alumnos.",
        distractors=(
            "Declara que muchas instancias de esta entidad pertenecen a una sola de otra entidad.",
            "Hace que la colección se guarde como texto en una sola columna de la tabla.",
            "Limita la relación a un único elemento aunque el campo sea una lista.",
        ),
        youtube_query="JPA @OneToMany mappedBy explicado",
    ),
    Concept(
        id="jpa.many-to-one",
        title="@ManyToOne",
        topic=T.JPA,
        summary="Relaciona muchas instancias con una sola de otra entidad, como pedidos con su usuario.",
        explanation="Es el lado que guarda la clave foránea: la tabla orders tiene una columna user_id. Se suele "
                    "acompañar de @JoinColumn para darle nombre a esa columna.\n\n"
                    "Con fetch = FetchType.LAZY el usuario no se carga hasta que accedes a él, evitando "
                    "consultas innecesarias.",
        analogy="Es como muchos alumnos que apuntan en su ficha el nombre del mismo profesor.",
        distractors=(
            "Declara que una instancia de esta entidad tiene una lista de muchas instancias de otra.",
            "Fusiona varias tablas en una sola al arrancar la aplicación.",
            "Obliga a que cada valor del campo sea distinto en toda la tabla.",
        ),
        youtube_query="JPA @ManyToOne @JoinColumn",
    ),
    Concept(
        id="jpa.one-to-one",
        title="@OneToOne",
        topic=T.JPA,
        summary="Relaciona cada instancia con exactamente una de otra entidad, como usuario y perfil.",
        explanation="Una de las dos tablas guarda la clave foránea de la otra. Se usa para separar datos que van "
                    "juntos pero que conviene tener en tablas distintas (datos opcionales, pesados o "
                    "sensibles).",
        analogy="Es como una persona y su pasaporte: cada pasaporte pertenece a una sola persona y viceversa.",
        distractors=(
            "Relaciona una instancia con muchas de otra entidad, como un profesor con sus alumnos.",
            "Hace que la entidad solo pueda tener una fila en toda la tabla.",
            "Copia los campos de la otra entidad dentro de esta al guardarla.",
        ),
        youtube_query="JPA @OneToOne ejemplo",
    ),
    Concept(
        id="jpa.many-to-many",
        title="@ManyToMany",
        topic=T.JPA,
        summary="Relaciona muchas instancias con muchas de otra entidad mediante una tabla intermedia.",
        explanation="Por ejemplo, estudiantes y cursos: un estudiante tiene varios cursos y un curso varios "
                    "estudiantes. JPA crea una tabla intermedia con las dos claves foráneas.\n\n"
                    "Si la relación necesita datos propios (fecha de inscripción, nota), conviene modelar la "
                    "tabla intermedia como una entidad con dos @ManyToOne.",
        analogy="Es como las listas de reproducción: una canción está en muchas listas y cada lista tiene muchas canciones.",
        distractors=(
            "Declara que una instancia de esta entidad se relaciona con exactamente una de otra.",
            "Duplica la entidad en varias bases de datos para repartir la carga.",
            "Permite que un mismo campo guarde valores de tipos distintos.",
        ),
        youtube_query="JPA @ManyToMany tabla intermedia",
    ),
    Concept(
        id="jpa.join-column",
        title="@JoinColumn",
        topic=T.JPA,
        summary="Define la columna de clave foránea que une la entidad con la relacionada (user_id).",
        explanation="Acompaña a @ManyToOne o @OneToOne en el lado que guarda la referencia. "
                    "@JoinColumn(name = \"user_id\") hace que la tabla tenga una columna user_id con el id del "
                    "usuario relacionado.",
        analogy="Es el hilo que ata dos fichas del archivador: en una ficha apuntas el número de la otra.",
        distractors=(
            "Une dos columnas de la tabla en una sola al guardar la entidad.",
            "Hace que el campo se incluya automáticamente en todas las consultas SQL con JOIN.",
            "Crea un índice de búsqueda de texto completo sobre el campo.",
        ),
        youtube_query="JPA @JoinColumn clave foránea",
    ),
    # --- Spring Data -----------------------------------------------------------------
    Concept(
        id="data.jpa-repository",
        title="JpaRepository",
        topic=T.DATA,
        summary="Obtiene sin escribir código los métodos CRUD, más paginación y ordenación.",
        explanation="Al declarar interface UserRepository extends JpaRepository<User, Long>, Spring Data genera "
                    "en tiempo de ejecución una implementación con todos esos métodos. User es la entidad y Long "
                    "el tipo de su @Id.\n\n"
                    "Además puedes declarar métodos como findByEmail(String email) y Spring deduce la consulta "
                    "a partir del nombre.",
        analogy="Es como contratar un archivero ya formado: sabe guardar, buscar y tirar fichas sin que le expliques cómo.",
        distractors=(
            "Convierte la interfaz en un controlador REST que expone la tabla en la API.",
            "Obliga a escribir a mano la implementación SQL de cada método de la interfaz.",
            "Crea una copia en memoria de la tabla que no se guarda en la base de datos.",
        ),
        youtube_query="Spring Data JpaRepository explicado",
    ),
    Concept(
        id="data.crud-repository",
        title="CrudRepository",
        topic=T.DATA,
        summary="Obtiene sin escribir código las operaciones básicas de crear, leer, actualizar y borrar.",
        explanation="CrudRepository es la interfaz más básica de Spring Data con métodos como save, findById, "
                    "findAll, count y deleteById. JpaRepository la amplía con paginación, ordenación y "
                    "operaciones por lotes.\n\n"
                    "Igual que JpaRepository, Spring genera la implementación en tiempo de ejecución.",
        analogy="Es el kit básico de herramientas: lo imprescindible, sin los accesorios del kit profesional.",
        distractors=(
            "Genera automáticamente los endpoints REST de creación, lectura, actualización y borrado.",
            "Registra la interfaz como una tabla nueva en la base de datos.",
            "Obliga a que todas las operaciones se ejecuten en modo solo lectura.",
        ),
        youtube_query="CrudRepository vs JpaRepository",
    ),
    Concept(
        id="data.query",
        title="@Query",
        topic=T.DATA,
        summary="Define a mano la consulta (JPQL o SQL) del método en lugar de deducirla de su nombre.",
        explanation="Cuando el nombre del método no basta (consultas con varias condiciones, joins, LIKE…), "
                    "@Query(\"SELECT u FROM User u WHERE …\") permite escribirla tú.\n\n"
                    "Por defecto es JPQL, que trabaja con entidades y campos Java; con nativeQuery = true "
                    "puedes escribir SQL de la base de datos.",
        analogy="Es darle al archivero una instrucción exacta por escrito en vez de confiar en que adivine qué buscas.",
        distractors=(
            "Hace que el método del repositorio se ejecute automáticamente cada cierto tiempo.",
            "Registra la consulta en el log sin ejecutarla contra la base de datos.",
            "Convierte el resultado del método en un parámetro de la URL.",
        ),
        youtube_query="Spring Data @Query JPQL",
    ),
    # --- Validación y errores -----------------------------------------------------------
    Concept(
        id="validation.valid",
        title="@Valid",
        topic=T.VALIDATION,
        summary="Pide validar las reglas del objeto (como @NotBlank) antes de ejecutar el método.",
        explanation="Si el objeto recibido incumple alguna regla, Spring no entra al método y responde con un "
                    "error 400 (lanza MethodArgumentNotValidException), que puedes personalizar con un "
                    "@ExceptionHandler.\n\n"
                    "Las reglas se declaran en los campos del DTO con anotaciones de Jakarta Validation.",
        analogy="Es el control de seguridad del aeropuerto: si tu equipaje no cumple las normas, no llegas a la puerta de embarque.",
        distractors=(
            "Marca el método como válido para que Spring lo incluya en la documentación de la API.",
            "Comprueba que el usuario ha iniciado sesión antes de ejecutar el método.",
            "Guarda el objeto en la base de datos solo si todos sus campos están vacíos.",
        ),
        youtube_query="Spring Boot @Valid validación DTO",
    ),
    Concept(
        id="validation.not-blank",
        title="@NotBlank",
        topic=T.VALIDATION,
        summary="Exige que el texto no sea nulo, ni vacío, ni solo espacios al validar el objeto.",
        explanation="Es una regla de Jakarta Validation. Por sí sola no hace nada: se comprueba cuando el objeto "
                    "se valida, por ejemplo al recibirlo con @Valid en un controlador.\n\n"
                    "Se diferencia de @NotNull (solo prohíbe null) y de @NotEmpty (prohíbe null y \"\", pero "
                    "acepta \"   \").",
        analogy="Es el asterisco rojo de un formulario: ese campo hay que rellenarlo de verdad.",
        distractors=(
            "Rellena automáticamente el campo con un texto por defecto si llega vacío o nulo.",
            "Elimina los espacios en blanco del texto antes de guardarlo.",
            "Impide que el campo aparezca en la respuesta JSON cuando está vacío.",
        ),
        youtube_query="@NotBlank vs @NotNull vs @NotEmpty",
    ),
    Concept(
        id="errors.exception-handler",
        title="@ExceptionHandler",
        topic=T.ERRORS,
        summary="Define el método que responde cuando se lanza cierto tipo de excepción.",
        explanation="Con @ExceptionHandler(UserNotFoundException.class), cada vez que un controlador lance esa "
                    "excepción Spring ejecuta este método, que puede devolver un 404 con un mensaje claro en "
                    "lugar de un error 500 genérico.\n\n"
                    "Dentro de una clase @RestControllerAdvice se aplica a todos los controladores.",
        analogy="Es el protocolo de emergencias: ante un tipo concreto de incidente, ya está escrito qué hacer.",
        distractors=(
            "Evita que el método lance excepciones capturándolas todas y descartándolas.",
            "Reintenta automáticamente el método cuando falla hasta que funcione.",
            "Registra la excepción en la base de datos para consultarla más tarde.",
        ),
        youtube_query="Spring @ExceptionHandler manejo de errores",
    ),
    Concept(
        id="errors.controller-advice",
        title="@RestControllerAdvice",
        topic=T.ERRORS,
        summary="Centraliza en una clase el manejo de excepciones de todos los controladores.",
        explanation="En lugar de repetir try/catch en cada controlador, una clase @RestControllerAdvice reúne los "
                    "métodos @ExceptionHandler y Spring los aplica a toda la aplicación.\n\n"
                    "@ControllerAdvice es la versión que trabaja con vistas; @RestControllerAdvice añade "
                    "@ResponseBody para devolver datos.",
        analogy="Es el departamento de atención al cliente: todas las quejas, vengan de donde vengan, se gestionan en un solo sitio.",
        distractors=(
            "Da consejos de rendimiento sobre los controladores al arrancar la aplicación.",
            "Registra un controlador REST adicional con rutas de administración.",
            "Intercepta las peticiones para exigir autenticación en todos los controladores.",
        ),
        youtube_query="Spring @RestControllerAdvice global exception handler",
    ),
)
